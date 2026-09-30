import { api, h, toast } from '/web/api.js';
import { icon } from '/web/icons.js';

let session = null;
let pending = null;
export async function loadSession(force = false) {
  if (force) session = null;
  if (session) return session;
  if (!pending) pending = api.get('/api/auth/session').then(value => {
    session = value; updateAccount(); return value;
  }).finally(() => { pending = null; });
  return pending;
}
export function clearSession() { session = null; }
function updateAccount() {
  document.getElementById('accountEmail').textContent = session?.user?.email || '';
  const button = document.getElementById('accountAction');
  button.textContent = session?.enabled === false ? 'Local demo' : session?.user ? 'Sign out' : 'Sign in';
  button.disabled = session?.enabled === false;
  button.onclick = async () => {
    if (!session?.user) { location.hash = '#/signin'; return; }
    button.disabled = true;
    try { await api.post('/api/auth/signout', {}); clearSession(); await loadSession(); location.hash = '#/signin'; }
    catch (error) { toast(error.message, true); }
    finally { button.disabled = false; }
  };
}
export function setupTheme() {
  const root = document.documentElement;
  let saved = '';
  try { saved = localStorage.getItem('portfolio-theme') || ''; } catch (_) {}
  const apply = theme => {
    root.dataset.theme = theme;
    try { localStorage.setItem('portfolio-theme', theme); } catch (_) {}
    const button = document.getElementById('themeToggle');
    button.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`);
    button.replaceChildren(icon(theme === 'dark' ? 'sun' : 'moon', { size: 18 }));
  };
  apply(saved === 'dark' || (!saved && matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light');
  document.getElementById('themeToggle').onclick = () => apply(root.dataset.theme === 'dark' ? 'light' : 'dark');
}
export function renderAuth({ main, mode = 'signin', onSuccess }) {
  const signup = mode === 'signup';
  const email = h('input', { id:'auth-email', name:'email', type:'email', autocomplete:'email', required:true, maxlength:254 });
  const password = h('input', { id:'auth-password', name:'password', type:'password', autocomplete:signup ? 'new-password' : 'current-password', required:true, minlength:12, maxlength:72 });
  const error = h('p', { class:'auth-error', role:'alert', 'aria-live':'polite' });
  const submit = h('button', { class:'btn primary', type:'submit' }, signup ? 'Create account' : 'Sign in');
  const form = h('form', { class:'auth-form', onsubmit:async event => {
    event.preventDefault(); if (submit.disabled) return;
    error.textContent = ''; submit.disabled = true;
    try {
      await api.post(`/api/auth/${signup ? 'signup' : 'signin'}`, { email:email.value.trim(), password:password.value });
      password.value = ''; clearSession(); await loadSession(); onSuccess();
    } catch (failure) { error.textContent = failure.message || 'Could not sign in. Please try again.'; }
    finally { submit.disabled = false; }
  } }, h('label', { class:'auth-field', for:'auth-email' }, 'Email address', email),
  h('label', { class:'auth-field', for:'auth-password' }, 'Password', password),
  signup ? h('p', { class:'auth-note' }, 'Use at least 12 characters. Password reset by email is not available yet.') : null,
  error, submit);
  main.replaceChildren(h('div', { class:'auth-page' },
    h('section', { class:'auth-intro' }, h('span', { class:'eyebrow' }, 'DEMO STUDIO'),
      h('h1', {}, 'Your product, ready to explore.'),
      h('p', {}, 'Create a guided demo from your documents, images and product knowledge. Review the facts and story before publishing.'),
      ...[['upload','Add your own product material'],['check-circle','Review six clear approval cards'],['play','Rehearse and share the experience']].map(([name,text]) => h('div', { class:'auth-step' }, icon(name), text))),
    h('section', { class:'auth-card', 'aria-labelledby':'auth-title' },
      h('h2', { id:'auth-title' }, signup ? 'Create your workspace' : 'Welcome back'),
      h('p', {}, signup ? 'Start with a ready example or your own sources.' : 'Sign in to your private demos and customer sessions.'), form,
      h('p', { class:'auth-foot' }, signup ? 'Already have an account? ' : 'New to Demo Studio? ', h('a', { href:signup ? '#/signin' : '#/signup' }, signup ? 'Sign in' : 'Create an account')),
      h('button', { class:'btn', disabled:true, type:'button', title:'Google sign-in is not configured' }, 'Google sign-in unavailable'),
      !signup ? h('p', { class:'auth-note' }, 'Password reset by email is not available yet.') : null)));
  email.focus();
}

export function exampleButton(navigate) {
  const label = document.createTextNode('Try with an example');
  const button = h('button', { class:'btn', 'aria-live':'polite', 'aria-busy':'false', onclick:async () => {
    if (button.disabled) return;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    label.nodeValue = 'Preparing example…';
    try { const demo = await api.post('/api/examples', {}); navigate(`#/studio/${demo.id}/rehearse`); }
    catch (error) { toast(error.message || 'The example could not load. Please try again.', true); }
    finally {
      button.disabled = false;
      button.setAttribute('aria-busy', 'false');
      label.nodeValue = 'Try with an example';
    }
  } }, icon('play', { size:16 }), label);
  return button;
}
