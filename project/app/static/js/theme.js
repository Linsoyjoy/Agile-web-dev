function toggleTheme() {
  var html = document.documentElement;
  var next = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-bs-theme', next);
  localStorage.setItem('chessmate-theme', next);
  updateToggleButton(next);
}

function updateToggleButton(theme) {
  var btn = document.getElementById('theme-toggle');
  if (btn) btn.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
}

document.addEventListener('DOMContentLoaded', function() {
  var theme = document.documentElement.getAttribute('data-bs-theme') || 'light';
  updateToggleButton(theme);
});
