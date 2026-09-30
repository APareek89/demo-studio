// Lucide ISC icons, vendored locally. Keep semantic aliases used by the product.
const aliases = { close: 'X', agent: 'Bot', chart: 'ChartColumn', flask: 'FlaskConical',
  message: 'MessageSquare', grid: 'LayoutGrid', file: 'FileText', volume: 'Volume2',
  'volume-off': 'VolumeX', restart: 'RotateCcw', expand: 'Maximize', stop: 'Square',
  edit: 'Pencil', trash: 'Trash2', settings: 'SlidersHorizontal', 'check-circle': 'CircleCheck',
  'alert-circle': 'CircleAlert' };
export function icon(name, { size = 20, className = '' } = {}) {
  const key = aliases[name] || name.split('-').map(s => s[0].toUpperCase()+s.slice(1)).join('');
  const library = globalThis.lucide;
  return library.createElement(library.icons[key] || library.icons.Layers, {
    width: size, height: size, 'stroke-width': 1.7, 'aria-hidden': 'true', focusable: 'false',
    class: `ui-icon ${className}`.trim()
  });
}
