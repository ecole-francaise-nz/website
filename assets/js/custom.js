(() => {
  'use strict';
  const previewBanner = document.getElementById('staff-preview-banner');
  if (previewBanner) {
    const dismiss = previewBanner.querySelector('.preview-dismiss');
    try { previewBanner.hidden = sessionStorage.getItem('efia-preview-dismissed') === 'true'; } catch (_) {}
    dismiss.hidden = false;
    dismiss.addEventListener('click', () => {
      previewBanner.hidden = true;
      try { sessionStorage.setItem('efia-preview-dismissed', 'true'); } catch (_) {}
      document.querySelector('.brand')?.focus({preventScroll: true});
    });
  }
  const searchToggle = document.getElementById('site-search-toggle');
  const searchPanel = document.getElementById('site-search-panel');
  const searchInput = document.getElementById('site-search-query');
  if (searchToggle && searchPanel) {
    const setSearchOpen = open => {
      searchPanel.hidden = !open;
      searchToggle.setAttribute('aria-expanded', String(open));
      if (open) searchInput.focus();
    };
    searchToggle.addEventListener('click', () => setSearchOpen(searchPanel.hidden));
    document.addEventListener('keydown', event => {
      if (event.defaultPrevented || event.isComposing || event.repeat || event.altKey || document.querySelector('dialog[open]')) return;
      // Leave text entry, form controls and embedded editors to their own keys.
      const target = event.target;
      if (target.isContentEditable || target.closest?.('input, textarea, select, [role="textbox"], [role="combobox"]')) return;
      const slash = event.key === '/' && !event.metaKey && !event.ctrlKey;
      const commandK = event.key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey) && !event.shiftKey;
      if (!slash && !commandK) return;
      event.preventDefault();
      setSearchOpen(true);
    });
    searchPanel.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        setSearchOpen(false);
        const focusTarget = searchToggle.getClientRects().length ? searchToggle : document.querySelector('.menu-toggle');
        focusTarget?.focus();
      }
    });
    document.addEventListener('click', event => {
      if (!searchPanel.hidden && !searchPanel.contains(event.target) && !searchToggle.contains(event.target)) {
        setSearchOpen(false);
      }
    });
  }
  const menuToggle = document.querySelector('.menu-toggle');
  const navigation = document.getElementById('main-navigation');
  const submenuButtons = [...document.querySelectorAll('.submenu-toggle')];
  function closeSubmenus(except) {
    submenuButtons.forEach(button => {
      if (button !== except) {
        button.setAttribute('aria-expanded', 'false');
        document.getElementById(button.getAttribute('aria-controls')).hidden = true;
      }
    });
  }
  if (menuToggle) {
    menuToggle.addEventListener('click', () => {
      const open = navigation.classList.toggle('is-open');
      menuToggle.setAttribute('aria-expanded', String(open));
      if (!open) closeSubmenus();
    });
  }
  submenuButtons.forEach(button => button.addEventListener('click', () => {
    const panel = document.getElementById(button.getAttribute('aria-controls'));
    closeSubmenus(button);
    panel.hidden = !panel.hidden;
    button.setAttribute('aria-expanded', String(!panel.hidden));
  }));
  const desktopHover = window.matchMedia('(min-width: 1151px) and (hover: hover) and (pointer: fine)');
  submenuButtons.forEach(button => {
    const group = button.closest('.nav-group');
    const panel = document.getElementById(button.getAttribute('aria-controls'));
    let leaveTimer;
    group.addEventListener('pointerenter', event => {
      clearTimeout(leaveTimer);
      if (!desktopHover.matches || event.pointerType !== 'mouse') return;
      closeSubmenus(button);
      panel.hidden = false;
      button.setAttribute('aria-expanded', 'true');
    });
    group.addEventListener('pointerleave', event => {
      if (!desktopHover.matches || event.pointerType !== 'mouse') return;
      leaveTimer = setTimeout(() => {
        if (!group.contains(document.activeElement)) {
          panel.hidden = true;
          button.setAttribute('aria-expanded', 'false');
        }
      }, 180);
    });
    group.addEventListener('focusout', event => {
      // In the collapsed layout, closing on pointer-down focus changes would
      // move the next button before pointer-up and prevent its click firing.
      if (desktopHover.matches && !group.contains(event.relatedTarget) && !group.matches(':hover')) {
        panel.hidden = true;
        button.setAttribute('aria-expanded', 'false');
      }
    });
  });
  desktopHover.addEventListener('change', () => closeSubmenus());
  document.addEventListener('click', event => {
    if (!event.target.closest('.nav-group')) closeSubmenus();
  });
  navigation?.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const openButton = submenuButtons.find(button => button.getAttribute('aria-expanded') === 'true');
    if (openButton) { closeSubmenus(); openButton.focus(); }
    else if (navigation.classList.contains('is-open')) {
      navigation.classList.remove('is-open');
      menuToggle.setAttribute('aria-expanded', 'false');
      menuToggle.focus();
    }
  });
  const faqExpand = document.getElementById('faq-expand');
  if (faqExpand) {
    const questions = [...document.querySelectorAll('.faq-item')];
    const update = () => {
      const allOpen = questions.every(item => item.open);
      faqExpand.textContent = allOpen ? faqExpand.dataset.collapse : faqExpand.dataset.expand;
    };
    faqExpand.hidden = false;
    faqExpand.addEventListener('click', () => {
      const open = !questions.every(item => item.open);
      questions.forEach(item => { item.open = open; });
      update();
    });
    questions.forEach(item => item.addEventListener('toggle', update));
  }
  const localDate = new Intl.DateTimeFormat('en-CA', { timeZone: 'Pacific/Auckland', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const part = type => localDate.find(item => item.type === type).value;
  const today = `${part('year')}-${part('month')}-${part('day')}`;
  document.querySelectorAll('[data-term-start]').forEach(row => {
    const current = today >= row.dataset.termStart && today <= row.dataset.termEnd;
    row.classList.toggle('is-current', current);
    row.querySelector('.current-badge').hidden = !current;
  });
  const dialog = document.getElementById('photo-dialog');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const links = [...document.querySelectorAll('.gallery-item')];
  const photo = document.getElementById('lightbox-image');
  const caption = document.getElementById('photo-caption');
  const counter = document.getElementById('photo-counter');
  const previous = dialog.querySelector('.lightbox-prev');
  const next = dialog.querySelector('.lightbox-next');
  let group = [], index = 0, opener;
  function show(offset = 0) {
    index = (index + offset + group.length) % group.length;
    const item = group[index];
    photo.src = item.href;
    photo.alt = item.dataset.caption;
    caption.textContent = item.dataset.caption;
    counter.textContent = `${index + 1} / ${group.length}`;
    previous.hidden = next.hidden = group.length < 2;
  }
  links.forEach(link => link.addEventListener('click', event => {
    // Modified clicks retain the normal open-image-in-new-tab behaviour.
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    opener = link;
    group = links.filter(item => item.dataset.gallery === link.dataset.gallery);
    index = group.indexOf(link);
    show();
    dialog.showModal();
    document.body.classList.add('gallery-open');
    dialog.querySelector('.lightbox-close').focus();
  }));
  previous.addEventListener('click', () => show(-1));
  next.addEventListener('click', () => show(1));
  dialog.querySelector('.lightbox-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    document.body.classList.remove('gallery-open');
    opener?.focus();
  });
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowRight') { event.preventDefault(); show(1); }
    if (event.key === 'ArrowLeft') { event.preventDefault(); show(-1); }
  });
  let touchStart;
  photo.addEventListener('touchstart', event => {
    if (event.touches.length === 1) touchStart = { x: event.touches[0].clientX, y: event.touches[0].clientY };
    else touchStart = null;
  }, { passive: true });
  photo.addEventListener('touchend', event => {
    if (!touchStart || event.changedTouches.length !== 1) return;
    const dx = event.changedTouches[0].clientX - touchStart.x;
    const dy = event.changedTouches[0].clientY - touchStart.y;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) show(dx < 0 ? 1 : -1);
    touchStart = null;
  }, { passive: true });
})();
