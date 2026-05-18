/* ── Dark Mode Toggle ──────────────────────────────────────── */
(function () {
  const ROOT = document.documentElement;
  const STORAGE_KEY = 'elmanara-theme';

  function applyTheme(theme) {
    ROOT.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
  }

  // Respect saved preference or OS preference
  const saved = localStorage.getItem(STORAGE_KEY);
  const preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  applyTheme(saved || preferred);

  document.addEventListener('DOMContentLoaded', function () {
    const btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.addEventListener('click', function () {
        const current = ROOT.getAttribute('data-theme');
        applyTheme(current === 'dark' ? 'light' : 'dark');
      });
    }

    /* ── Mobile Nav Burger ─────────────────────────────────── */
    const burger = document.getElementById('nav-burger');
    const navLinks = document.getElementById('nav-links');
    if (burger && navLinks) {
      burger.addEventListener('click', function () {
        navLinks.classList.toggle('open');
        burger.classList.toggle('open');
      });
    }

    /* ── Package Hour Slider ───────────────────────────────── */
    const slider = document.getElementById('hours-slider');
    if (slider) {
      const hoursDisplay = document.getElementById('hours-display');
      const priceDisplay = document.getElementById('price-display');
      const pphDisplay   = document.getElementById('pph-display');
      const savingsEl    = document.getElementById('savings-badge');
      const purchaseBtn  = document.getElementById('purchase-btn');
      const pkgIdInput   = document.getElementById('pkg-id-input');

      // Build lookup from data attributes on each pkg card
      const pkgCards = document.querySelectorAll('.pkg-card[data-hours]');
      const pkgMap = {};
      pkgCards.forEach(card => {
        const h = parseInt(card.dataset.hours, 10);
        pkgMap[h] = {
          price: parseFloat(card.dataset.price),
          pph: parseFloat(card.dataset.pph),
          savings: parseInt(card.dataset.savings || '0', 10),
          pkgId: card.dataset.pkgId,
          featured: card.dataset.featured === '1',
        };
      });

      const STEP = 8;
      const MIN  = 8;
      const MAX  = 64;

      function updateSlider(val) {
        const pct = ((val - MIN) / (MAX - MIN)) * 100;
        slider.style.setProperty('--range-pct', pct + '%');

        if (hoursDisplay) hoursDisplay.textContent = val;

        const info = pkgMap[val];
        if (!info) return;

        // Highlight active card
        pkgCards.forEach(c => c.classList.toggle('selected', parseInt(c.dataset.hours, 10) === val));

        if (priceDisplay) priceDisplay.textContent = `$${info.price.toFixed(2)}`;
        if (pphDisplay)   pphDisplay.textContent   = `$${info.pph.toFixed(2)} / hr`;
        if (pkgIdInput)   pkgIdInput.value         = info.pkgId;

        if (savingsEl) {
          if (info.savings > 0) {
            savingsEl.textContent = `Save ${info.savings}%`;
            savingsEl.style.display = 'inline-block';
          } else {
            savingsEl.style.display = 'none';
          }
        }
      }

      slider.addEventListener('input', () => updateSlider(parseInt(slider.value, 10)));

      // Click on card selects it
      pkgCards.forEach(card => {
        card.addEventListener('click', function () {
          const h = parseInt(this.dataset.hours, 10);
          slider.value = h;
          updateSlider(h);
        });
      });

      // Init
      updateSlider(parseInt(slider.value, 10));
    }

    /* ── Referral copy button ──────────────────────────────── */
    const copyBtn = document.getElementById('copy-referral');
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        const code = this.dataset.code;
        navigator.clipboard.writeText(code).then(() => {
          const original = this.textContent;
          this.textContent = '✅ Copied!';
          setTimeout(() => { this.textContent = original; }, 2000);
        });
      });
    }
  });
})();
