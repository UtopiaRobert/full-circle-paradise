(() => {
  'use strict';

  const galleries = window.FIELDSTATION_GALLERIES || {};
  const PREVIEW_LIMIT = 20;

  let activeItems = [];
  let activeIndex = 0;
  let lastFocused = null;
  let touchStartX = null;

  const viewer = document.createElement('div');
  viewer.className = 'fs-gallery-viewer';
  viewer.hidden = true;
  viewer.setAttribute('aria-hidden', 'true');
  viewer.innerHTML = `
    <div class="fs-gallery-viewer__stage" role="dialog" aria-modal="true" aria-label="Photograph gallery">
      <button class="fs-gallery-viewer__close" type="button" aria-label="Close gallery">×</button>
      <button class="fs-gallery-viewer__nav fs-gallery-viewer__previous" type="button" aria-label="Previous photograph">‹</button>
      <div class="fs-gallery-viewer__image-wrap">
        <img class="fs-gallery-viewer__image" alt="">
      </div>
      <p class="fs-gallery-viewer__caption"><span class="fs-gallery-viewer__caption-text"></span><span class="fs-gallery-viewer__count"></span></p>
      <button class="fs-gallery-viewer__nav fs-gallery-viewer__next" type="button" aria-label="Next photograph">›</button>
    </div>`;
  document.body.appendChild(viewer);

  const stage = viewer.querySelector('.fs-gallery-viewer__stage');
  const image = viewer.querySelector('.fs-gallery-viewer__image');
  const caption = viewer.querySelector('.fs-gallery-viewer__caption-text');
  const count = viewer.querySelector('.fs-gallery-viewer__count');
  const closeButton = viewer.querySelector('.fs-gallery-viewer__close');
  const previousButton = viewer.querySelector('.fs-gallery-viewer__previous');
  const nextButton = viewer.querySelector('.fs-gallery-viewer__next');

  function updateViewer() {
    const item = activeItems[activeIndex];
    if (!item) return;

    image.src = item.src;
    image.alt = item.alt || item.caption || 'Full Circle Paradise photograph';
    caption.textContent = item.caption || item.alt || '';
    count.textContent = `${activeIndex + 1} of ${activeItems.length}`;

    previousButton.hidden = activeItems.length < 2;
    nextButton.hidden = activeItems.length < 2;

    const nextItem = activeItems[(activeIndex + 1) % activeItems.length];
    if (nextItem && nextItem.src) {
      const preload = new Image();
      preload.src = nextItem.src;
    }
  }

  function openViewer(items, index = 0, trigger = null) {
    if (!Array.isArray(items) || !items.length) return;
    activeItems = items;
    activeIndex = Math.max(0, Math.min(index, items.length - 1));
    lastFocused = trigger || document.activeElement;
    updateViewer();
    viewer.hidden = false;
    viewer.setAttribute('aria-hidden', 'false');
    document.body.classList.add('fs-gallery-open');
    closeButton.focus();
  }

  function closeViewer() {
    viewer.hidden = true;
    viewer.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('fs-gallery-open');
    image.removeAttribute('src');
    if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus();
  }

  function move(step) {
    if (!activeItems.length) return;
    activeIndex = (activeIndex + step + activeItems.length) % activeItems.length;
    updateViewer();
  }

  closeButton.addEventListener('click', closeViewer);
  previousButton.addEventListener('click', () => move(-1));
  nextButton.addEventListener('click', () => move(1));

  viewer.addEventListener('click', (event) => {
    if (event.target === viewer) closeViewer();
  });

  stage.addEventListener('touchstart', (event) => {
    touchStartX = event.changedTouches[0]?.clientX ?? null;
  }, { passive: true });

  stage.addEventListener('touchend', (event) => {
    if (touchStartX === null) return;
    const endX = event.changedTouches[0]?.clientX ?? touchStartX;
    const delta = endX - touchStartX;
    touchStartX = null;
    if (Math.abs(delta) > 45) move(delta > 0 ? -1 : 1);
  }, { passive: true });

  document.addEventListener('keydown', (event) => {
    if (viewer.hidden) return;
    if (event.key === 'Escape') closeViewer();
    if (event.key === 'ArrowLeft') move(-1);
    if (event.key === 'ArrowRight') move(1);
  });

  function makeThumbnail(item, index, items) {
    const button = document.createElement('button');
    button.className = 'fieldstation-gallery__thumb';
    button.type = 'button';
    button.dataset.caption = item.caption || '';
    button.setAttribute('aria-label', `Open photograph ${index + 1}: ${item.caption || item.alt || ''}`);

    const thumb = document.createElement('img');
    thumb.src = item.thumb || item.src;
    thumb.alt = item.alt || item.caption || 'Full Circle Paradise photograph';
    thumb.loading = 'lazy';
    thumb.decoding = 'async';
    button.appendChild(thumb);

    button.addEventListener('click', () => openViewer(items, index, button));
    return button;
  }

  document.querySelectorAll('[data-fieldstation-gallery]').forEach((section) => {
    const key = section.dataset.fieldstationGallery;
    const items = Array.isArray(galleries[key]) ? galleries[key] : [];
    const preview = section.querySelector('[data-gallery-preview]');
    const countTarget = section.querySelector('[data-gallery-count]');
    const browseButton = section.querySelector('[data-gallery-open]');

    if (countTarget) countTarget.textContent = String(items.length);

    if (!preview || !items.length) {
      if (preview) preview.innerHTML = '<p class="fieldstation-gallery__empty">No photographs have been added to this gallery yet.</p>';
      if (browseButton) browseButton.hidden = true;
      return;
    }

    items.slice(0, PREVIEW_LIMIT).forEach((item, index) => {
      preview.appendChild(makeThumbnail(item, index, items));
    });

    if (browseButton) browseButton.addEventListener('click', () => openViewer(items, 0, browseButton));
  });
})();
