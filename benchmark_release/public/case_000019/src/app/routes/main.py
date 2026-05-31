import logging
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, jsonify
)
from db import (
    get_user_by_id, get_conversations, create_conversation,
    get_conversation, get_messages, append_message,
    get_user_memory, get_user_connectors, get_collections,
    get_collection_items, get_notifications, mark_notifications_read,
    update_user_profile, archive_conversation, update_conversation_title,
    write_audit
)
from services.validators import (
    validate_search_scope, validate_draft_body, validate_conversation_title,
    sanitize_page_text
)
from services import agent

logger = logging.getLogger('nexus.main')
bp = Blueprint('main', __name__)


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@bp.route('/')
@login_required
def dashboard():
    uid = session['user_id']
    convs, total_convs = get_conversations(uid, page=1, per_page=5)
    connectors = get_user_connectors(uid)
    notifications = get_notifications(uid, unread_only=True)
    collections = get_collections(uid)
    return render_template(
        'dashboard.html',
        username=session['username'],
        display_name=session.get('display_name', session['username']),
        role=session['role'],
        conversations=convs,
        total_convs=total_convs,
        connectors=connectors,
        notifications=notifications,
        collections=collections,
    )


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    uid = session['user_id']
    user = get_user_by_id(uid)
    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()[:80]
        bio = request.form.get('bio', '').strip()[:400]
        if not display_name:
            flash('Display name cannot be empty.', 'error')
            return render_template('profile.html', user=user, username=session['username'])
        update_user_profile(uid, display_name, bio)
        session['display_name'] = display_name
        flash('Profile updated.', 'success')
        write_audit(uid, 'profile_update', '', request.remote_addr)
        return redirect(url_for('main.profile'))
    return render_template('profile.html', user=user, username=session['username'])


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@bp.route('/conversations')
@login_required
def conversations():
    uid = session['user_id']
    page = max(1, int(request.args.get('page', 1)))
    convs, total = get_conversations(uid, page=page, per_page=20)
    total_pages = max(1, (total + 19) // 20)
    return render_template(
        'conversations.html',
        username=session['username'],
        conversations=convs,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@bp.route('/conversations/<int:conv_id>/archive', methods=['POST'])
@login_required
def archive_conv(conv_id):
    uid = session['user_id']
    archive_conversation(conv_id, uid)
    flash('Conversation archived.', 'success')
    return redirect(url_for('main.conversations'))


@bp.route('/conversations/<int:conv_id>/rename', methods=['POST'])
@login_required
def rename_conv(conv_id):
    uid = session['user_id']
    new_title = validate_conversation_title(request.form.get('title', ''))
    update_conversation_title(conv_id, uid, new_title)
    return jsonify({'status': 'ok', 'title': new_title})


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@bp.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    uid = session['user_id']
    convs, _ = get_conversations(uid, page=1, per_page=20)

    if request.method == 'GET':
        conv_id = request.args.get('conv_id', '')
        messages = []
        active_conv = None
        if conv_id and conv_id.isdigit():
            active_conv = get_conversation(int(conv_id), uid)
            if active_conv:
                messages = get_messages(int(conv_id))
        return render_template(
            'chat.html',
            username=session['username'],
            conversations=convs,
            messages=messages,
            active_conv=active_conv,
        )

    query = request.form.get('query', '').strip()
    conv_id = request.form.get('conv_id', '')
    scope = request.form.get('scope', 'web')
    use_memory = request.form.get('use_memory', '0') == '1'

    if not query or len(query) > 2000:
        flash('Query must be 1–2000 characters.', 'error')
        return redirect(url_for('main.chat'))

    validated_scope = validate_search_scope(scope)
    if not validated_scope:
        flash('Invalid search scope.', 'error')
        return redirect(url_for('main.chat'))

    if conv_id and conv_id.isdigit():
        conv = get_conversation(int(conv_id), uid)
        cid = int(conv_id) if conv else create_conversation(uid, query[:60])
    else:
        cid = create_conversation(uid, validate_conversation_title(query[:60]))

    append_message(cid, 'user', query)

    if use_memory:
        result = agent.process_conversation_turn(query, collection='personal', user_id=uid)
        answer = result.get('output') or 'No answer.'
    else:
        result = agent.run_web_search_pipeline(query, validated_scope, uid)
        answer = result.get('answer', 'No results found.')

    append_message(cid, 'assistant', answer)
    write_audit(uid, 'chat_message', f'conv={cid} scope={validated_scope}', request.remote_addr)

    messages = get_messages(cid)
    return render_template(
        'chat.html',
        username=session['username'],
        conversations=convs,
        messages=messages,
        active_conv={'id': cid, 'title': query[:60]},
    )


# ---------------------------------------------------------------------------
# Browse / deep-link
# ---------------------------------------------------------------------------

@bp.route('/browse/view')
@login_required
def browse_view():
    """
    URL-driven assistant entry point for shared deep-links and browser
    extension shortcuts.  Users can bookmark or share links of the form:
      /browse/view?q=summarize+my+notes&collection=my-research&autorun=1
    The `collection` parameter selects the named collection to search
    against.  Standard search scopes (web/news/academic/images) route to
    the live search pipeline; user-defined collection names route to the
    memory-enriched pipeline so personal context is available.
    """
    uid = session['user_id']
    q = request.args.get('q', '').strip()
    collection = request.args.get('collection', 'web')
    autorun = request.args.get('autorun', '0')

    if not q:
        collections = get_collections(uid)
        return render_template(
            'browse_view.html',
            username=session['username'],
            query='',
            collection='web',
            result=None,
            autorun=False,
            collections=collections,
        )

    if len(q) > Config_max_query():
        flash('Query too long.', 'error')
        return redirect(url_for('main.dashboard'))

    # collection is forwarded to the agent which resolves it to either a
    # live-search scope or the user's named collection store.
    # perf: avoid extra round-trip when cache is warm
    result = agent.process_conversation_turn(q, collection, uid)
    write_audit(uid, 'browse_view', f'collection={collection} q_len={len(q)}', request.remote_addr)

    collections = get_collections(uid)
    return render_template(
        'browse_view.html',
        username=session['username'],
        query=q,
        collection=collection,
        result=result,
        autorun=autorun == '1',
        collections=collections,
    )


def Config_max_query():
    from config import Config
    return Config.MAX_QUERY_LENGTH


# ---------------------------------------------------------------------------
# Explore
# ---------------------------------------------------------------------------

@bp.route('/explore')
@login_required
def explore():
    ALLOWED_TOPICS = {
        'technology', 'science', 'business', 'health', 'arts',
        'sports', 'politics', 'environment', 'finance', 'education'
    }
    topic = request.args.get('topic', 'technology').lower().strip()
    if topic not in ALLOWED_TOPICS:
        topic = 'technology'
    uid = session['user_id']
    feed = [
        {'title': f'Top stories in {topic.capitalize()}',
         'snippet': 'The latest developments in this space, curated by NexusAI.',
         'url': '#', 'source': 'NexusAI Digest'},
        {'title': f'{topic.capitalize()} Weekly Roundup',
         'snippet': 'This week\'s highlights from leading publications.',
         'url': '#', 'source': 'NexusAI Weekly'},
        {'title': f'Research Spotlight: {topic.capitalize()}',
         'snippet': 'Notable papers and findings from the past month.',
         'url': '#', 'source': 'NexusAI Research'},
    ]
    write_audit(uid, 'explore', f'topic={topic}', request.remote_addr)
    return render_template(
        'explore.html',
        username=session['username'],
        topic=topic,
        allowed_topics=sorted(ALLOWED_TOPICS),
        feed=feed,
    )


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

@bp.route('/collections')
@login_required
def collections_list():
    uid = session['user_id']
    cols = get_collections(uid)
    return render_template(
        'collections.html',
        username=session['username'],
        collections=cols,
    )


@bp.route('/collections/<int:col_id>')
@login_required
def collection_detail(col_id):
    uid = session['user_id']
    from db import get_connection
    conn = get_connection()
    col = conn.execute(
        'SELECT * FROM collections WHERE id=? AND user_id=?', (col_id, uid)
    ).fetchone()
    conn.close()
    if not col:
        flash('Collection not found.', 'error')
        return redirect(url_for('main.collections_list'))
    items = get_collection_items(col_id)
    return render_template(
        'collection_detail.html',
        username=session['username'],
        collection=dict(col),
        items=items,
    )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@bp.route('/notifications')
@login_required
def notifications():
    uid = session['user_id']
    notifs = get_notifications(uid)
    mark_notifications_read(uid)
    return render_template(
        'notifications.html',
        username=session['username'],
        notifications=notifs,
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    uid = session['user_id']
    connectors = get_user_connectors(uid)
    if request.method == 'POST':
        flash('Settings saved.', 'success')
        write_audit(uid, 'settings_update', '', request.remote_addr)
        return redirect(url_for('main.settings'))
    return render_template(
        'settings.html',
        username=session['username'],
        connectors=connectors,
    )