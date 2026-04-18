// Pratibmb Clinical — minimal motion JS (scroll reveal + reading progress + nav state)
(function () {
  'use strict';

  // ── Reading progress bar (article pages only) ──
  var progress = document.querySelector('.cn-progress');
  if (progress) {
    var article = document.querySelector('.cn-article-page');
    function updateProgress() {
      if (!article) return;
      var rect = article.getBoundingClientRect();
      var docTop = window.pageYOffset || document.documentElement.scrollTop;
      var articleTop = rect.top + docTop;
      var articleHeight = article.scrollHeight;
      var winH = window.innerHeight;
      var scrolled = docTop - articleTop + winH * 0.5;
      var max = Math.max(articleHeight - winH * 0.5, 1);
      var pct = Math.max(0, Math.min(100, (scrolled / max) * 100));
      progress.style.width = pct + '%';
    }
    window.addEventListener('scroll', updateProgress, { passive: true });
    window.addEventListener('resize', updateProgress, { passive: true });
    updateProgress();
  }

  // ── Sticky nav: add .scrolled class when scrolled ──
  var nav = document.querySelector('.cn-nav');
  if (nav) {
    function updateNav() {
      if (window.scrollY > 16) nav.classList.add('scrolled');
      else nav.classList.remove('scrolled');
    }
    window.addEventListener('scroll', updateNav, { passive: true });
    updateNav();
  }

  // ── Scroll reveal: add .is-visible to .cn-reveal elements when in view ──
  var revealEls = document.querySelectorAll('.cn-reveal');
  if (revealEls.length && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('is-visible');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    // Fallback: just show everything
    revealEls.forEach(function (el) { el.classList.add('is-visible'); });
  }

  // ── Smooth scroll for anchor links ──
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener('click', function (ev) {
      var id = a.getAttribute('href');
      if (id.length < 2) return;
      var target = document.querySelector(id);
      if (!target) return;
      ev.preventDefault();
      var y = target.getBoundingClientRect().top + window.pageYOffset - 80;
      window.scrollTo({ top: y, behavior: 'smooth' });
    });
  });
})();
