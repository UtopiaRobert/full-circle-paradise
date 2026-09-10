
(() => {
  const button = document.querySelector('.menu-button');
  const nav = document.querySelector('.primary-nav');

  if (nav && !nav.querySelector('.personal-home-link')) {
    const personal = document.createElement('a');
    personal.href = 'https://utopiarobert.github.io/';
    personal.textContent = 'Robert';
    personal.className = 'personal-home-link';
    personal.setAttribute('aria-label', 'Robert Redecker personal journal');
    nav.prepend(personal);
  }
  if (button && nav) {
    button.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      button.setAttribute('aria-expanded', String(open));
    });
  }

  const box = document.querySelector('.lightbox');
  if (!box) return;
  const boxImage = box.querySelector('img');
  const caption = box.querySelector('p');
  const close = box.querySelector('button');
  let previousFocus = null;

  const hide = () => {
    box.hidden = true;
    box.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    if (previousFocus) previousFocus.focus();
  };

  document.querySelectorAll('[data-lightbox]').forEach((image) => {
    image.setAttribute('tabindex', '0');
    image.setAttribute('role', 'button');
    image.setAttribute('aria-label', `${image.alt}. Open larger image.`);
    const show = () => {
      previousFocus = image;
      boxImage.src = image.src;
      boxImage.alt = image.alt;
      const figureCaption = image.closest('figure')?.querySelector('figcaption');
      caption.textContent = figureCaption ? figureCaption.textContent.trim() : image.alt;
      box.hidden = false;
      box.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      close.focus();
    };
    image.addEventListener('click', show);
    image.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); show(); }
    });
  });
  close.addEventListener('click', hide);
  box.addEventListener('click', (event) => { if (event.target === box) hide(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !box.hidden) hide(); });
})();
