const $ = id => document.getElementById(id);

export function initImageViewer({element, resourceLink}) {
  function originalFilename(url) {
    if (url.origin === 'https://ids.si.edu' && url.pathname === '/ids/download' &&
        url.searchParams.getAll('id').length === 1) {
      const filename = url.searchParams.get('id');
      if (/^[A-Za-z0-9_-]{1,128}\.(?:jpg|jpeg|tif|tiff)$/.test(filename)) return filename;
    }
    return null;
  }

  function formatFileSize(bytes) {
    if (!Number.isSafeInteger(bytes) || bytes <= 0) return 'Size unavailable';
    const [amount, unit] = bytes >= 1000000 ? [bytes / 1000000, 'MB']
      : bytes >= 1000 ? [bytes / 1000, 'KB'] : [bytes, 'B'];
    return new Intl.NumberFormat('en-US', {maximumFractionDigits:1}).format(amount) + ' ' + unit;
  }

  async function showFileSize(filename, label, signal) {
    label.textContent = 'Checking size…';
    try {
      const response = await fetch('/api/image-size?' + new URLSearchParams({file: filename}), {signal});
      if (!response.ok) throw new Error('Could not check file size.');
      const {bytes} = await response.json();
      if (!signal.aborted) label.textContent = formatFileSize(bytes);
    } catch {
      if (!signal.aborted) label.textContent = 'Size unavailable';
    }
  }

  const viewer = $('image-viewer');
  const original = $('image-viewer-image');
  let imageDetails;
  let fallbackPreview;

  function showOriginalImage(resources, previewUrl, fallbackUrl, mediaName) {
    const status = $('image-viewer-status');
    $('image-viewer-title').textContent = mediaName;
    imageDetails = new AbortController();
    const list = element('ul');
    list.className = 'image-viewer-files';
    const files = [...resources].sort((left, right) => left.format.localeCompare(right.format));
    for (const resource of files) {
      const format = resource.format.toUpperCase();
      const dimensions = resource.declared_width && resource.declared_height
        ? resource.declared_width + ' × ' + resource.declared_height + ' px' : 'Dimensions not declared';
      const action = resourceLink(resource.url, '');
      if (action.tagName !== 'A') continue;
      const size = element('span', 'Size unavailable');
      const label = element('span');
      label.append(format + ' (' + dimensions + ', ', size, ')');
      action.prepend(label);
      action.append(' ', $('image-download-icon').content.cloneNode(true));
      const filename = originalFilename(new URL(action.href));
      if (filename) showFileSize(filename, size, imageDetails.signal);
      const row = element('li');
      row.append(action);
      list.append(row);
    }
    const source = $('image-viewer-source');
    source.replaceChildren(list);
    if (list.childElementCount) {
      const heading = element('h3', 'Download Image');
      heading.className = 'image-viewer-file-title';
      source.prepend(heading);
    }
    original.alt = 'Image preview for ' + mediaName;
    original.hidden = true;
    fallbackPreview = fallbackUrl;
    status.textContent = previewUrl ? 'Loading image preview…' : 'Preview unavailable. Use the file links below.';
    viewer.showModal();
    if (previewUrl) original.src = previewUrl;
  }

  original.addEventListener('load', () => {
    if (!viewer.open) return;
    original.hidden = false;
    $('image-viewer-status').textContent = '';
  });
  original.addEventListener('error', () => {
    if (!viewer.open) return;
    if (fallbackPreview) {
      original.src = fallbackPreview;
      fallbackPreview = null;
      return;
    }
    $('image-viewer-status').textContent = 'Preview unavailable. Use the file links below.';
  });
  viewer.addEventListener('close', () => {
    imageDetails?.abort();
    original.removeAttribute('src');
    original.hidden = true;
  });

  function resourcePreview(image, files, source) {
    const [resource] = files;
    const isIiif = resource.source === 'iiif';
    const link = resourceLink(resource.url, isIiif ? 'View image' : 'View source', isIiif);
    if (link.tagName !== 'A') return link;
    const mediaName = image.media_id || 'Image';
    const hasMediaId = /^[A-Za-z0-9_-]{1,128}$/.test(image.media_id || '');
    const previewUrl = kind => '/api/image-preview?' + new URLSearchParams({id:image.media_id, kind});
    const thumbnailUrl = hasMediaId ? previewUrl('thumbnail') : null;
    if (isIiif && hasMediaId &&
        link.href === 'https://ids.si.edu/ids/iiif/' + image.media_id + '/full/full/0/default.jpg') {
      // The public image endpoint can reject browser navigation while serving JPEGs to the bridge.
      link.href = previewUrl('iiif');
    }

    let control = link;
    if (resource.source === 'open_access') {
      control = element('button', 'View image');
      control.type = 'button';
      control.setAttribute('aria-haspopup', 'dialog');
      control.addEventListener('click', () => {
        showOriginalImage(files, hasMediaId ? previewUrl('preview') : null, thumbnailUrl, mediaName);
      });
    } else if (isIiif) {
      const label = element('span');
      label.className = 'external-link';
      label.append(...link.childNodes);
      link.classList.remove('external-link');
      link.append(label);
    }

    control.classList.add('resource-preview');
    control.setAttribute('aria-label', control.textContent + ' for ' + mediaName + ' from ' + source +
      (isIiif ? ' (opens in a new tab)' : ''));
    if (thumbnailUrl) {
      const thumbnail = element('img');
      thumbnail.alt = '';
      thumbnail.referrerPolicy = 'no-referrer';
      thumbnail.loading = 'lazy';
      thumbnail.addEventListener('error', () => { thumbnail.hidden = true; });
      thumbnail.src = thumbnailUrl;
      control.prepend(thumbnail);
    }
    return control;
  }

  function bindImageHelp(button, help, preferredWidth = 260) {
    let pinned = false;
    let closeTimer;
    function cancelHoverClose() {
      clearTimeout(closeTimer);
    }
    function scheduleHoverClose(event) {
      if (event.pointerType !== 'mouse') return;
      cancelHoverClose();
      closeTimer = setTimeout(() => {
        if (!pinned && !help.matches(':focus-within') && help.matches(':popover-open')) {
          help.hidePopover();
        }
      }, 160);
    }

    button.addEventListener('pointerenter', event => {
      if (event.pointerType !== 'mouse') return;
      cancelHoverClose();
      if (!help.matches(':popover-open')) help.showPopover({source: button});
    });
    button.addEventListener('pointerleave', scheduleHoverClose);
    help.addEventListener('pointerenter', cancelHoverClose);
    help.addEventListener('pointerleave', scheduleHoverClose);
    button.addEventListener('click', event => {
      if (help.matches(':popover-open') && pinned) return;
      if (help.matches(':popover-open')) event.preventDefault();
      pinned = true;
      cancelHoverClose();
    });
    help.addEventListener('beforetoggle', event => {
      if (event.newState !== 'open') {
        pinned = false;
        cancelHoverClose();
        return;
      }
      const trigger = button.getBoundingClientRect();
      const viewportWidth = document.documentElement.clientWidth;
      const viewportHeight = window.innerHeight;
      const width = Math.min(preferredWidth, viewportWidth - 24);
      help.style.width = width + 'px';
      help.style.left = Math.max(12, Math.min(trigger.left, viewportWidth - width - 12)) + 'px';
      const opensBelow = trigger.bottom <= viewportHeight / 2;
      help.style.top = opensBelow ? trigger.bottom + 4 + 'px' : 'auto';
      help.style.bottom = opensBelow ? 'auto' : viewportHeight - trigger.top + 4 + 'px';
    });
    button.setAttribute('popovertarget', help.id);
  }

  function showAssets(data, results) {
    for (const warning of data.warnings) results.append(element('p', warning));
    if (!data.images.length) {
      results.append(element('p', 'No image resources returned.'));
      return;
    }
    const wrapper = element('div');
    wrapper.className = 'table-wrap';
    const table = element('table');
    table.className = 'image-assets-table';
    table.setAttribute('aria-label', 'Image resources');
    table.setAttribute('role', 'table');
    const heading = element('tr');
    const columns = [
      {label: 'Media ID', description: 'The Smithsonian identifier for the image. Two resources can share the same media ID.'},
      {
        label: 'Source',
        description: 'Open Access API and IIIF identify where the image link came from. The IIIF manifest lists the images associated with this record.',
        link: data.manifest_url,
        linkLabel: 'IIIF Manifest',
      },
      {label: 'Declared dimensions', description: 'The width and height in pixels reported for this resource, when available.'},
      {
        label: 'Usage',
        description: 'The label reflects the rights information supplied for each image. See Smithsonian’s terms for guidance on reuse.',
        link: 'https://www.si.edu/termsofuse',
        linkLabel: 'Terms of Use',
      },
      {label: 'Resource', description: 'IIIF images open in a new tab. Open Access images show the available download formats.'},
    ];
    for (const [index, column] of columns.entries()) {
      const cell = element('th');
      cell.scope = 'col';
      const title = element('div', column.label);
      title.className = 'column-with-help';
      const button = element('button');
      button.type = 'button';
      button.className = 'help-trigger';
      button.setAttribute('aria-label', 'About ' + column.label);
      const icon = element('span', '?');
      icon.setAttribute('aria-hidden', 'true');
      button.append(icon);

      const help = element('div', column.description);
      help.id = 'image-column-help-' + index;
      help.className = 'help-tooltip column-help';
      help.setAttribute('popover', 'auto');
      bindImageHelp(button, help);
      if (column.link) help.append(resourceLink(column.link, column.linkLabel, true));

      title.append(button, help);
      cell.append(title);
      heading.append(cell);
    }
    const thead = element('thead');
    thead.append(heading);
    table.append(thead);
    const body = element('tbody');
    body.setAttribute('role', 'rowgroup');
    for (const image of data.images) {
      const openAccess = image.resources.filter(resource => resource.source === 'open_access');
      const groups = image.resources
        .filter(resource => resource.source === 'iiif')
        .map(resource => [resource]);
      if (openAccess.length) groups.unshift(openAccess);

      for (const files of groups) {
        const isIiif = files[0].source === 'iiif';
        const source = isIiif ? 'IIIF' : 'Open Access API';
        const sizes = new Set(files.map(resource =>
          resource.declared_width && resource.declared_height
            ? resource.declared_width + ' × ' + resource.declared_height : 'Not declared'
        ));
        const dimensions = sizes.size === 1 ? sizes.values().next().value : 'Varies by format';
        const row = element('tr');
        const access = element('td');
        const isCc0 = image.media_access === 'CC0' && image.usage_label === 'CC0';
        const usage = $(isCc0 ? 'cc-zero-icon' : 'usage-terms-help').content.cloneNode(true);
        const help = usage.querySelector('.usage-help');
        help.id = 'image-usage-help-' + body.rows.length;
        bindImageHelp(usage.querySelector('button'), help, 320);
        access.append(usage);
        const link = element('td');
        link.append(resourcePreview(image, files, source));
        const sourceCell = element('td');
        if (isIiif && data.manifest_url) {
          sourceCell.append(resourceLink(data.manifest_url, 'IIIF Manifest', true));
        } else {
          sourceCell.textContent = source;
        }
        row.setAttribute('role', 'row');
        row.append(element('td', image.media_id || 'Unknown'), sourceCell, element('td', dimensions), access, link);
        for (const [index, cell] of [...row.cells].entries()) {
          cell.setAttribute('role', 'cell');
          if (cell === link) continue;
          const label = element('span', columns[index].label);
          label.className = 'image-field-label';
          cell.prepend(label);
        }
        body.append(row);
      }
    }
    table.append(body);
    wrapper.append(table);
    const usageLink = element('p');
    usageLink.className = 'image-usage-link';
    usageLink.append(resourceLink('https://www.si.edu/termsofuse', 'Terms of Use', true));
    results.append(wrapper, usageLink);
  }

  return showAssets;
}
