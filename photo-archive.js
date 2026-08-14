(() => {
  'use strict';

  const items = Array.isArray(window.PHOTO_ARCHIVE)
    ? window.PHOTO_ARCHIVE
    : [];

  const grid = document.querySelector('[data-photo-archive-grid]');
  const filters = document.querySelector('[data-photo-archive-filters]');
  const count = document.querySelector('[data-photo-archive-count]');

  if (!grid || !filters) return;

  let activeFilter = 'All';
  let visibleItems = [];

  const categories = Array.from(
    new Set(items.flatMap(item => item.categories || []))
  );

  const viewer = document.createElement('div');
  viewer.className = 'fs-gallery-viewer';
  viewer.hidden = true;
  viewer.setAttribute('aria-hidden', 'true');

  viewer.innerHTML = `
    <div class="fs-gallery-viewer__stage"
         role="dialog"
         aria-modal="true"
         aria-label="Photo Archive viewer">
      <button class="fs-gallery-viewer__close"
              type="button"
              aria-label="Close photograph">×</button>

      <button class="fs-gallery-viewer__nav fs-gallery-viewer__previous"
              type="button"
              aria-label="Previous photograph">‹</button>

      <div class="fs-gallery-viewer__image-wrap">
        <img class="fs-gallery-viewer__image" alt="">
      </div>

      <p class="fs-gallery-viewer__caption">
        <span class="fs-gallery-viewer__caption-text"></span>
        <span class="fs-gallery-viewer__count"></span>
      </p>

      <button class="fs-gallery-viewer__nav fs-gallery-viewer__next"
              type="button"
              aria-label="Next photograph">›</button>
    </div>
  `;

  document.body.appendChild(viewer);

  const image = viewer.querySelector('.fs-gallery-viewer__image');
  const caption = viewer.querySelector('.fs-gallery-viewer__caption-text');
  const position = viewer.querySelector('.fs-gallery-viewer__count');
  const close = viewer.querySelector('.fs-gallery-viewer__close');
  const previous = viewer.querySelector('.fs-gallery-viewer__previous');
  const next = viewer.querySelector('.fs-gallery-viewer__next');

  let activeIndex = 0;

  function updateViewer() {
    const item = visibleItems[activeIndex];
    if (!item) return;

    image.src = item.src;
    image.alt = item.alt || item.caption || 'Full Circle Paradise photograph';
    caption.textContent = item.caption || item.alt || '';
    position.textContent =
      `${activeIndex + 1} of ${visibleItems.length}`;
  }

  function openViewer(index) {
    activeIndex = index;
    updateViewer();
    viewer.hidden = false;
    viewer.setAttribute('aria-hidden', 'false');
    document.body.classList.add('fs-gallery-open');
    close.focus();
  }

  function closeViewer() {
    viewer.hidden = true;
    viewer.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('fs-gallery-open');
    image.removeAttribute('src');
  }

  function move(amount) {
    if (!visibleItems.length) return;

    activeIndex =
      (activeIndex + amount + visibleItems.length)
      % visibleItems.length;

    updateViewer();
  }

  close.addEventListener('click', closeViewer);
  previous.addEventListener('click', () => move(-1));
  next.addEventListener('click', () => move(1));

  viewer.addEventListener('click', event => {
    if (event.target === viewer) closeViewer();
  });

  document.addEventListener('keydown', event => {
    if (viewer.hidden) return;

    if (event.key === 'Escape') closeViewer();
    if (event.key === 'ArrowLeft') move(-1);
    if (event.key === 'ArrowRight') move(1);
  });

  function renderFilters() {
    ['All', ...categories].forEach(name => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = name;
      button.className = 'photo-archive-filter';

      if (name === activeFilter) {
        button.classList.add('active');
      }

      button.addEventListener('click', () => {
        activeFilter = name;
        redraw();
      });

      filters.appendChild(button);
    });
  }

  function renderGrid() {
    grid.innerHTML = '';

    visibleItems = activeFilter === 'All'
      ? items
      : items.filter(item =>
          (item.categories || []).includes(activeFilter)
        );

    if (count) {
      count.textContent =
        `${visibleItems.length} photograph${visibleItems.length === 1 ? '' : 's'}`;
    }

    visibleItems.forEach((item, index) => {
      const button = document.createElement('button');
      button.className = 'photo-archive-card';
      button.type = 'button';

      const img = document.createElement('img');
      img.src = item.thumb || item.src;
      img.alt = item.alt || item.caption || '';
      img.loading = 'lazy';
      img.decoding = 'async';

      button.appendChild(img);

      button.addEventListener('click', () => openViewer(index));

      grid.appendChild(button);
    });
  }

  function redraw() {
    filters.innerHTML = '';
    renderFilters();
    renderGrid();
  }

  redraw();
})();
