// Small progressive enhancements; every page works without JavaScript.
// No inline scripts anywhere: the Content Security Policy only allows this file.

(function () {
  'use strict';

  // Show/hide password: <button data-password-toggle="input-id" data-label-show data-label-hide>.
  document.querySelectorAll('[data-password-toggle]').forEach(function (button) {
    var input = document.getElementById(button.getAttribute('data-password-toggle'));
    if (!input) return;
    button.addEventListener('click', function () {
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      button.textContent = show ? button.dataset.labelHide : button.dataset.labelShow;
      button.setAttribute('aria-pressed', String(show));
      input.focus();
    });
  });

  // Close the mobile menu after following an in-page link.
  var nav = document.getElementById('site-nav');
  if (nav && window.bootstrap) {
    nav.addEventListener('click', function (event) {
      var link = event.target.closest('a[href*="#"]');
      if (link && nav.classList.contains('show')) {
        window.bootstrap.Collapse.getOrCreateInstance(nav).hide();
      }
    });
  }
})();
