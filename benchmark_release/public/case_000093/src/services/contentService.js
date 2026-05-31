'use strict';

// NOTE: In production this would pull from a CMS or S3-backed cache.
// For now, content is held in memory and refreshed on deploy.
// TODO: add stale-while-revalidate logic when traffic grows past ~500 rps

const BLOG_POSTS = [
  {
    slug: 'intro',
    title: 'Introduction',
    author: 'Alice Mercer',
    date: '2024-01-10',
    tags: ['general', 'welcome'],
    summary: 'Welcome to our blog — what to expect from us in 2024.',
    body: '<p>Welcome to our blog! This is the intro post. We plan to cover engineering, culture, and product updates throughout the year.</p>'
  },
  {
    slug: 'hello-world',
    title: 'Hello World',
    author: 'Bob Tran',
    date: '2024-01-15',
    tags: ['engineering'],
    summary: 'Our very first engineering post.',
    body: '<p>First post! We talk about our stack choices and why we picked SvelteKit for the frontend.</p>'
  },
  {
    slug: 'scaling-postgres',
    title: 'Scaling Postgres to 10M rows',
    author: 'Carol Singh',
    date: '2024-02-03',
    tags: ['engineering', 'database'],
    summary: 'Lessons learned from a large Postgres migration.',
    body: '<p>We recently migrated a monolithic MySQL instance to Postgres. Here are the key takeaways.</p>'
  },
  {
    slug: 'design-tokens',
    title: 'Design Tokens in Practice',
    author: 'Dave Kim',
    date: '2024-02-20',
    tags: ['design', 'frontend'],
    summary: 'How we implemented a token-based design system.',
    body: '<p>Design tokens reduce drift between Figma and code. We walk through our setup.</p>'
  },
  {
    slug: 'incident-postmortem-jan',
    title: 'Incident Postmortem — January Outage',
    author: 'Alice Mercer',
    date: '2024-02-28',
    tags: ['ops', 'reliability'],
    summary: 'What caused the January outage and what we fixed.',
    body: '<p>On January 23rd we experienced a 47-minute partial outage. This post explains the timeline and mitigations.</p>'
  }
];

const STATIC_PAGES = {
  about: {
    title: 'About Us',
    body: '<p>We are a small product team building tools for developers. Founded in 2019, headquartered in Amsterdam.</p>'
  },
  contact: {
    title: 'Contact',
    body: '<p>Reach us at hello@example.com or via the form below. We try to respond within one business day.</p>'
  }
};

function getPostBySlug(slug) {
  return BLOG_POSTS.find(p => p.slug === slug) || null;
}

function listPosts({ page = 1, tag = null } = {}) {
  const PAGE_SIZE = 10;
  let posts = BLOG_POSTS.slice();
  if (tag) {
    posts = posts.filter(p => p.tags.includes(tag));
  }
  const total = posts.length;
  const start = (page - 1) * PAGE_SIZE;
  return {
    posts: posts.slice(start, start + PAGE_SIZE),
    total,
    page,
    pages: Math.ceil(total / PAGE_SIZE)
  };
}

function getStaticPage(name) {
  return STATIC_PAGES[name] || null;
}

// TODO: i18n — wrap titles/bodies in locale-aware fetch when multi-lang ships
module.exports = { getPostBySlug, listPosts, getStaticPage };