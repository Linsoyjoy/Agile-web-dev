function toggleTheme() {
  var html = document.documentElement;
  var next = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-bs-theme', next);
  localStorage.setItem('chessmate-theme', next);
  updateToggleButton(next);
}

function updateToggleButton(theme) {
  var label = document.getElementById('theme-label');
  var icon = document.getElementById('theme-icon');
  if (label) label.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
  if (icon) icon.className = theme === 'dark' ? 'bi bi-sun me-2' : 'bi bi-moon me-2';
}

document.addEventListener('DOMContentLoaded', function() {
  var theme = document.documentElement.getAttribute('data-bs-theme') || 'light';
  updateToggleButton(theme);
});
