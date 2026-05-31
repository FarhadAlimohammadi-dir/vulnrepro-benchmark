function logTo(el, text) {
  const node = document.getElementById(el);
  if (node) node.textContent += text + '\n';
}

async function openProject(id) {
  try {
    const r = await fetch('/projects/' + id + '/open', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    });
    const j = await r.json();
    logTo('actionLog', 'open: ' + JSON.stringify(j, null, 2));
  } catch (e) {
    logTo('actionLog', 'error: ' + e.message);
  }
}

async function formatProject(id) {
  try {
    const r = await fetch('/projects/' + id + '/format', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ formatter: 'prettier' })
    });
    const j = await r.json();
    logTo('actionLog', 'format: ' + JSON.stringify(j, null, 2));
  } catch (e) {
    logTo('actionLog', 'error: ' + e.message);
  }
}