function initAdirsViewer(root) {
    const payload = JSON.parse(root.dataset.adirsPayload || '{}');
    const labelsToggle = root.querySelector('[data-adirs-labels]');
    const stats = root.querySelector('[data-adirs-stats]');
    const status = root.querySelector('[data-adirs-status]');
    const editorTabs = root.querySelector('[data-adirs-editor-tabs]');
    const editor = root.querySelector('[data-adirs-editor]');
    const areasEditor = root.querySelector('[data-adirs-areas]');
    const resetButton = root.querySelector('[data-adirs-reset]');
    const changesInput = root.querySelector('[data-adirs-changes-input]');
    const canvas = root.querySelector('[data-adirs-canvas]');
    const context = canvas ? canvas.getContext('2d') : null;

    if (!canvas || !context || !payload.style_entries) {
        return;
    }

    const state = {
        payload,
        baseStyleEntries: structuredClone(payload.base_style_entries || []),
        styleEntries: structuredClone(payload.style_entries || []),
        baseAreas: structuredClone(payload.base_areas || []),
        areaEntries: structuredClone(payload.look_source?.areas || []),
        activeAreaIndex: null,
        activeEditorGroup: 'general',
        scale: 1,
        offsetX: 0,
        offsetY: 0,
        fitScale: 1,
        fitOffsetX: 0,
        fitOffsetY: 0,
        dragging: false,
        lastX: 0,
        lastY: 0,
        showLabels: payload.changes?.meta?.show_labels ?? true,
    };

    labelsToggle.checked = state.showLabels;

    function setStatus(text) {
        if (status) {
            status.textContent = text;
        }
    }

    function colorCsvToRgba(value) {
        const parts = (value || '255,255,255,255').split(',').map((part) => Number.parseFloat(part.trim()));
        const [red = 255, green = 255, blue = 255, alpha = 255] = parts;

        return `rgba(${red}, ${green}, ${blue}, ${Math.max(0, Math.min(1, alpha / 255))})`;
    }

    function parseColorCsv(value) {
        const parts = (value ?? '').split(',').map((part) => Number.parseInt(part.trim(), 10));
        const [red = 255, green = 255, blue = 255, alpha = 255] = parts;

        return {
            red: Math.max(0, Math.min(255, red || 0)),
            green: Math.max(0, Math.min(255, green || 0)),
            blue: Math.max(0, Math.min(255, blue || 0)),
            alpha: Math.max(0, Math.min(255, alpha || 0)),
        };
    }

    function rgbToHex({ red, green, blue }) {
        return `#${[red, green, blue].map((value) => value.toString(16).padStart(2, '0')).join('')}`;
    }

    function hexToRgb(value) {
        const safe = (value || '#ffffff').replace('#', '');

        return {
            red: Number.parseInt(safe.slice(0, 2), 16),
            green: Number.parseInt(safe.slice(2, 4), 16),
            blue: Number.parseInt(safe.slice(4, 6), 16),
        };
    }

    function colorPartsToCsv({ red, green, blue, alpha }) {
        return [red, green, blue, alpha].map((value) => Math.max(0, Math.min(255, value))).join(',');
    }

    function styleValue(key, fallback) {
        const entry = state.styleEntries.find((item) => item.key === key);

        if (!entry) {
            return fallback;
        }

        return entry.kind === 'color' ? colorCsvToRgba(entry.value) : entry.value;
    }

    function roadStyle(type) {
        const map = {
            0: ['Taxiway color', 'Taxiway thickness', 'rgba(45, 45, 45, 1)', 20],
            1: ['Terminal color', 'Terminal thickness', 'rgba(0, 0, 0, 1)', 10],
            2: ['Runway color', 'Runway thickness', 'rgba(15, 15, 15, 1)', 28],
            4: ['Road area color', 'Road area thickness', 'rgba(100, 100, 100, 1)', 3],
            5: ['Road area color', 'Road area thickness', 'rgba(100, 100, 100, 1)', 4],
        };

        const [colorKey, widthKey, fallbackColor, fallbackWidth] = map[type] ?? map[0];
        const width = Number.parseFloat(styleValue(widthKey, `${fallbackWidth}`));

        return {
            color: styleValue(colorKey, fallbackColor),
            width: Number.isFinite(width) && width > 0 ? width : fallbackWidth,
        };
    }

    function isDisplayLabel(name) {
        if (!name) {
            return false;
        }

        const value = name.trim().toLowerCase();

        return !(
            value.startsWith('gate_') ||
            /^carroad(?:[_a-z0-9]+)?$/.test(value) ||
            /^car_?traffic(?:[_a-z0-9]+)?$/.test(value) ||
            /^taxiway_?\d+[a-z]*$/.test(value) ||
            /^taxicar(?:[_a-z0-9]+)?$/.test(value)
        );
    }

    function editorGroups() {
        return [
            { key: 'general', label: 'General', keys: ['Background color', 'Rotation', 'Road area color', 'Road area thickness', 'Road outline color', 'Road outline thickness', 'Terminal color', 'Terminal thickness', 'Route color', 'Route thickness', 'Eye color', 'Eye width', 'Eye length', 'Airplane size', 'Airplane text size'] },
            { key: 'taxiways', label: 'Taxiways', keys: ['Taxiway color', 'Taxiway thickness', 'Road selected color'] },
            { key: 'points', label: 'Signs and holding points', keys: ['Road text background color', 'Road text color', 'Road text size', 'Road text distance', 'Point text background color', 'Point text color'] },
            { key: 'runways', label: 'Runways', keys: ['Runway color', 'Runway thickness', 'Road selected runway'] },
            { key: 'departures', label: 'Departures', keys: ['Airplane color departure', 'Airplane color callsign departure', 'Airplane selected color departure', 'Airplane selected color callsign departure'] },
            { key: 'arrivals', label: 'Arrivals', keys: ['Airplane color arrive', 'Airplane color callsign arrive', 'Airplane selected color arrive', 'Airplane selected color callsign arrive'] },
            { key: 'areas', label: 'Areas', keys: [] },
        ];
    }

    function groupForEntry(entry) {
        return editorGroups().find((group) => group.keys.includes(entry.key))?.key ?? 'general';
    }

    function updateStats() {
        if (!stats) {
            return;
        }

        const entries = [
            ['Airport', `${state.payload.airport.icao} · ${state.payload.airport.name}`],
            ['Database', state.payload.workspace.database],
            ['Instrument set', state.payload.workspace.instrument_set],
            ['Roads', String(state.payload.stats.roads)],
            ['Areas', String(state.payload.stats.areas)],
            ['Named points', String(state.payload.stats.named_points)],
        ];

        stats.innerHTML = entries.map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join('');
    }

    function syncChangesInput() {
        if (!changesInput) {
            return;
        }

        const styleOverrides = {};

        state.styleEntries.forEach((entry, index) => {
            if (entry.value !== state.baseStyleEntries[index]?.value) {
                styleOverrides[entry.key] = entry.value;
            }
        });

        const areaOverrides = state.areaEntries.map((area, index) => {
            const override = {};

            if (area.color_raw !== state.baseAreas[index]?.color_raw) {
                override.color_raw = area.color_raw;
            }

            return override;
        });

        changesInput.value = JSON.stringify({
            styles: styleOverrides,
            areas: areaOverrides,
            meta: {
                show_labels: state.showLabels,
            },
        });
    }

    function resizeCanvas() {
        const rect = canvas.getBoundingClientRect();
        canvas.width = Math.max(640, Math.floor(rect.width || 640));
        canvas.height = Math.max(480, Math.floor(rect.height || 480));
        fitView();
        render();
    }

    function collectBounds() {
        const bounds = {
            minX: Number.POSITIVE_INFINITY,
            maxX: Number.NEGATIVE_INFINITY,
            minZ: Number.POSITIVE_INFINITY,
            maxZ: Number.NEGATIVE_INFINITY,
        };

        function includePoint(point) {
            bounds.minX = Math.min(bounds.minX, point.x);
            bounds.maxX = Math.max(bounds.maxX, point.x);
            bounds.minZ = Math.min(bounds.minZ, point.z);
            bounds.maxZ = Math.max(bounds.maxZ, point.z);
        }

        state.payload.roads.forEach((road) => road.points.forEach(includePoint));
        state.payload.areas.forEach((area) => area.points.forEach(includePoint));
        state.payload.named_points.forEach((point) => includePoint(point));

        if (!Number.isFinite(bounds.minX)) {
            return { minX: -100, maxX: 100, minZ: -100, maxZ: 100 };
        }

        return bounds;
    }

    function fitView() {
        const bounds = collectBounds();
        const worldWidth = Math.max(1, bounds.maxX - bounds.minX);
        const worldHeight = Math.max(1, bounds.maxZ - bounds.minZ);
        const padding = 28;

        state.fitScale = Math.min((canvas.width - padding * 2) / worldWidth, (canvas.height - padding * 2) / worldHeight);

        const centerX = (bounds.minX + bounds.maxX) / 2;
        const centerZ = (bounds.minZ + bounds.maxZ) / 2;

        state.fitOffsetX = canvas.width / 2 - centerX * state.fitScale;
        state.fitOffsetY = canvas.height / 2 - centerZ * state.fitScale;
        state.scale = state.fitScale;
        state.offsetX = state.fitOffsetX;
        state.offsetY = state.fitOffsetY;
    }

    function toScreen(point) {
        return {
            x: point.x * state.scale + state.offsetX,
            y: canvas.height - (point.z * state.scale + state.offsetY),
        };
    }

    function toWorld(screenX, screenY) {
        return {
            x: (screenX - state.offsetX) / state.scale,
            z: ((canvas.height - screenY) - state.offsetY) / state.scale,
        };
    }

    function pointInPolygon(point, polygon) {
        let inside = false;

        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i, i += 1) {
            const xi = polygon[i].x;
            const zi = polygon[i].z;
            const xj = polygon[j].x;
            const zj = polygon[j].z;
            const intersects = ((zi > point.z) !== (zj > point.z))
                && (point.x < ((xj - xi) * (point.z - zi)) / ((zj - zi) || Number.EPSILON) + xi);

            if (intersects) {
                inside = !inside;
            }
        }

        return inside;
    }

    function areaIndexAtCanvasPoint(screenX, screenY) {
        const worldPoint = toWorld(screenX, screenY);

        for (let index = state.payload.areas.length - 1; index >= 0; index -= 1) {
            const area = state.payload.areas[index];

            if (area.points.length >= 3 && pointInPolygon(worldPoint, area.points)) {
                return index;
            }
        }

        return null;
    }

    function renderArea(area, index) {
        if (area.points.length < 3) {
            return;
        }

        context.beginPath();
        const first = toScreen(area.points[0]);
        context.moveTo(first.x, first.y);

        for (let pointIndex = 1; pointIndex < area.points.length; pointIndex += 1) {
            const point = toScreen(area.points[pointIndex]);
            context.lineTo(point.x, point.y);
        }

        context.closePath();
        context.fillStyle = colorCsvToRgba(area.color_raw ?? area.color);
        context.globalAlpha = 0.68;
        context.fill();
        context.globalAlpha = 1;

        if (state.activeAreaIndex === index) {
            context.save();
            context.strokeStyle = 'rgba(255, 214, 10, 1)';
            context.lineWidth = 8;
            context.stroke();
            context.restore();
        }
    }

    function renderRoad(road) {
        if (road.points.length < 2) {
            return;
        }

        const style = roadStyle(road.type);
        context.beginPath();
        const first = toScreen(road.points[0]);
        context.moveTo(first.x, first.y);

        for (let pointIndex = 1; pointIndex < road.points.length; pointIndex += 1) {
            const point = toScreen(road.points[pointIndex]);
            context.lineTo(point.x, point.y);
        }

        context.strokeStyle = style.color;
        context.lineWidth = Math.max(1, style.width * state.scale * 0.06);
        context.stroke();
    }

    function renderLabel(road) {
        if (!state.showLabels || !isDisplayLabel(road.name)) {
            return;
        }

        const point = toScreen(road.label);
        context.font = '11px "Instrument Sans", sans-serif';
        const paddingX = 5;
        const width = context.measureText(road.name).width + paddingX * 2;
        const boxX = point.x - width / 2;
        const boxY = point.y - 10;

        context.fillStyle = styleValue('Road text background color', 'rgba(0, 0, 0, 0.55)');
        context.fillRect(boxX, boxY, width, 16);
        context.fillStyle = styleValue('Road text color', 'rgba(255, 255, 255, 1)');
        context.fillText(road.name, boxX + paddingX, boxY + 12);
    }

    function renderNamedPoint(point) {
        const screen = toScreen(point);
        const text = point.name;

        context.font = '11px "Instrument Sans", sans-serif';
        const radius = 7;
        const textWidth = context.measureText(text).width;
        const boxWidth = textWidth + 12;
        const boxHeight = 18;
        const boxX = screen.x + 10;
        const boxY = screen.y - boxHeight / 2;

        context.fillStyle = styleValue('Point text background color', 'rgba(120, 120, 200, 1)');
        context.beginPath();
        context.arc(screen.x, screen.y, radius, 0, Math.PI * 2);
        context.fill();

        context.fillRect(boxX, boxY, boxWidth, boxHeight);
        context.fillStyle = styleValue('Point text color', 'rgba(1, 1, 1, 1)');
        context.fillText(text, boxX + 6, boxY + 12);
    }

    function render() {
        context.clearRect(0, 0, canvas.width, canvas.height);
        context.fillStyle = styleValue('Background color', 'rgba(0, 96, 119, 1)');
        context.fillRect(0, 0, canvas.width, canvas.height);
        state.payload.areas = state.payload.areas.map((area, index) => ({ ...area, color_raw: state.areaEntries[index]?.color_raw ?? area.color_raw }));
        state.payload.areas.forEach((area, index) => renderArea(area, index));
        state.payload.roads.forEach(renderRoad);
        state.payload.named_points.forEach(renderNamedPoint);
        state.payload.roads.forEach(renderLabel);
    }

    function buildEditor() {
        const groups = editorGroups().map((group) => ({
            ...group,
            entries: state.styleEntries.filter((entry) => groupForEntry(entry) === group.key),
        }));

        editorTabs.innerHTML = groups.map((group) => `
            <button type="button" class="adirs-subtab ${group.key === state.activeEditorGroup ? 'is-active' : ''}" data-editor-group="${group.key}">
                ${group.label}
            </button>
        `).join('');

        const activeGroup = groups.find((group) => group.key === state.activeEditorGroup) ?? groups[0];

        if (activeGroup.key === 'areas') {
            editor.innerHTML = `
                <div class="settings-copy">
                    The first pass supports area color overrides. Coordinate editing can build on this next.
                </div>
            `;
            areasEditor.hidden = false;
        } else {
            areasEditor.hidden = true;
        }

        if (activeGroup.key !== 'areas') {
            editor.innerHTML = activeGroup.entries.map((entry) => {
                const absoluteIndex = state.styleEntries.findIndex((item) => item.key === entry.key);

                if (entry.kind === 'color') {
                    const parts = parseColorCsv(entry.value);

                    return `
                        <label class="adirs-editor-row">
                            <span>${entry.key}</span>
                            <div class="adirs-editor-input adirs-editor-input-color">
                                <span class="adirs-swatch" style="background:${colorCsvToRgba(entry.value)}"></span>
                                <input type="color" value="${rgbToHex(parts)}" data-style-index="${absoluteIndex}" data-color-role="hex">
                                <input type="number" min="0" max="255" value="${parts.alpha}" data-style-index="${absoluteIndex}" data-color-role="alpha">
                                <input type="text" value="${entry.value}" data-style-index="${absoluteIndex}" data-color-role="raw">
                                <button type="button" class="button-link-muted" data-style-reset="${absoluteIndex}">Reset</button>
                            </div>
                        </label>
                    `;
                }

                return `
                    <label class="adirs-editor-row">
                        <span>${entry.key}</span>
                        <div class="adirs-editor-input">
                            <input type="text" value="${entry.value}" data-style-index="${absoluteIndex}">
                            <button type="button" class="button-link-muted" data-style-reset="${absoluteIndex}">Reset</button>
                        </div>
                    </label>
                `;
            }).join('');
        }

        editorTabs.querySelectorAll('[data-editor-group]').forEach((button) => {
            button.addEventListener('click', () => {
                state.activeEditorGroup = button.dataset.editorGroup;
                buildEditor();
            });
        });

        if (activeGroup.key === 'areas') {
            buildAreasEditor();
            return;
        }

        editor.querySelectorAll('input[data-style-index]').forEach((input) => {
            input.addEventListener('input', (event) => {
                const index = Number.parseInt(event.currentTarget.dataset.styleIndex, 10);
                const role = event.currentTarget.dataset.colorRole;

                if (!role) {
                    state.styleEntries[index].value = event.currentTarget.value.trim();
                    syncChangesInput();
                    render();
                    return;
                }

                const row = event.currentTarget.closest('.adirs-editor-input');
                const hexInput = row.querySelector('[data-color-role="hex"]');
                const alphaInput = row.querySelector('[data-color-role="alpha"]');
                const rawInput = row.querySelector('[data-color-role="raw"]');
                const swatch = row.querySelector('.adirs-swatch');
                let color = parseColorCsv(state.styleEntries[index].value);

                if (role === 'hex') {
                    color = { ...color, ...hexToRgb(event.currentTarget.value) };
                }

                if (role === 'alpha') {
                    color = { ...color, alpha: Number.parseInt(event.currentTarget.value || '255', 10) };
                }

                if (role === 'raw') {
                    color = parseColorCsv(event.currentTarget.value);
                }

                const nextValue = colorPartsToCsv(color);
                state.styleEntries[index].value = nextValue;
                hexInput.value = rgbToHex(color);
                alphaInput.value = String(color.alpha);
                rawInput.value = nextValue;
                swatch.style.background = colorCsvToRgba(nextValue);
                syncChangesInput();
                render();
            });
        });

        editor.querySelectorAll('[data-style-reset]').forEach((button) => {
            button.addEventListener('click', () => {
                const index = Number.parseInt(button.dataset.styleReset, 10);
                state.styleEntries[index].value = state.baseStyleEntries[index]?.value ?? '';
                syncChangesInput();
                buildEditor();
                render();
            });
        });
    }

    function buildAreasEditor() {
        if (state.activeEditorGroup !== 'areas') {
            areasEditor.innerHTML = '';
            return;
        }

        const orderedAreas = state.areaEntries.map((entry, index) => ({ entry, index }));

        if (state.activeAreaIndex !== null) {
            orderedAreas.sort((left, right) => {
                if (left.index === state.activeAreaIndex) {
                    return -1;
                }

                if (right.index === state.activeAreaIndex) {
                    return 1;
                }

                return left.index - right.index;
            });
        }

        areasEditor.innerHTML = orderedAreas.map(({ entry, index }) => {
            const parts = parseColorCsv(entry.color_raw);

            return `
                <div class="adirs-area-card ${state.activeAreaIndex === index ? 'is-active' : ''}">
                    <div class="adirs-area-head">
                        <strong>Area ${index + 1}</strong>
                        <button type="button" class="button-link-muted adirs-area-focus" data-area-focus="${index}">
                            ${state.activeAreaIndex === index ? 'Highlighted' : 'Highlight'}
                        </button>
                    </div>
                    <div class="adirs-area-meta">${entry.points.length} coordinates</div>
                    <div class="adirs-editor-input adirs-editor-input-color">
                        <span class="adirs-swatch" style="background:${colorCsvToRgba(entry.color_raw)}"></span>
                        <input type="color" value="${rgbToHex(parts)}" data-area-index="${index}" data-area-role="hex">
                        <input type="number" min="0" max="255" value="${parts.alpha}" data-area-index="${index}" data-area-role="alpha">
                        <input type="text" value="${entry.color_raw}" data-area-index="${index}" data-area-role="raw">
                        <button type="button" class="button-link-muted" data-area-reset="${index}">Reset</button>
                    </div>
                </div>
            `;
        }).join('');

        areasEditor.querySelectorAll('[data-area-focus]').forEach((button) => {
            button.addEventListener('click', () => {
                const index = Number.parseInt(button.dataset.areaFocus, 10);
                state.activeAreaIndex = state.activeAreaIndex === index ? null : index;
                buildAreasEditor();
                render();
            });
        });

        areasEditor.querySelectorAll('input[data-area-index]').forEach((input) => {
            input.addEventListener('input', (event) => {
                const index = Number.parseInt(event.currentTarget.dataset.areaIndex, 10);
                const role = event.currentTarget.dataset.areaRole;
                const row = event.currentTarget.closest('.adirs-editor-input');
                const hexInput = row.querySelector('[data-area-role="hex"]');
                const alphaInput = row.querySelector('[data-area-role="alpha"]');
                const rawInput = row.querySelector('[data-area-role="raw"]');
                const swatch = row.querySelector('.adirs-swatch');
                let color = parseColorCsv(state.areaEntries[index].color_raw);

                if (role === 'hex') {
                    color = { ...color, ...hexToRgb(event.currentTarget.value) };
                }

                if (role === 'alpha') {
                    color = { ...color, alpha: Number.parseInt(event.currentTarget.value || '255', 10) };
                }

                if (role === 'raw') {
                    color = parseColorCsv(event.currentTarget.value);
                }

                const nextValue = colorPartsToCsv(color);
                state.areaEntries[index].color_raw = nextValue;
                hexInput.value = rgbToHex(color);
                alphaInput.value = String(color.alpha);
                rawInput.value = nextValue;
                swatch.style.background = colorCsvToRgba(nextValue);
                syncChangesInput();
                render();
            });
        });

        areasEditor.querySelectorAll('[data-area-reset]').forEach((button) => {
            button.addEventListener('click', () => {
                const index = Number.parseInt(button.dataset.areaReset, 10);
                state.areaEntries[index].color_raw = state.baseAreas[index]?.color_raw ?? state.areaEntries[index].color_raw;
                syncChangesInput();
                buildAreasEditor();
                render();
            });
        });
    }

    function resetToBase() {
        state.styleEntries = structuredClone(state.baseStyleEntries);
        state.areaEntries = structuredClone(state.baseAreas);
        state.activeAreaIndex = null;
        state.showLabels = true;
        labelsToggle.checked = true;
        syncChangesInput();
        buildEditor();
        buildAreasEditor();
        render();
        setStatus('Reset ADIRS changes to the workspace base file.');
    }

    canvas.addEventListener('mousedown', (event) => {
        state.dragging = true;
        state.lastX = event.clientX;
        state.lastY = event.clientY;
    });

    window.addEventListener('mouseup', () => {
        state.dragging = false;
    });

    window.addEventListener('mousemove', (event) => {
        if (!state.dragging) {
            return;
        }

        state.offsetX += event.clientX - state.lastX;
        state.offsetY -= event.clientY - state.lastY;
        state.lastX = event.clientX;
        state.lastY = event.clientY;
        render();
    });

    canvas.addEventListener('wheel', (event) => {
        event.preventDefault();
        const zoom = event.deltaY > 0 ? 0.92 : 1.08;
        const worldX = (event.offsetX - state.offsetX) / state.scale;
        const worldZ = ((canvas.height - event.offsetY) - state.offsetY) / state.scale;

        state.scale = Math.max(0.001, Math.min(12, state.scale * zoom));
        state.offsetX = event.offsetX - worldX * state.scale;
        state.offsetY = (canvas.height - event.offsetY) - worldZ * state.scale;
        render();
    }, { passive: false });

    canvas.addEventListener('click', (event) => {
        if (state.activeEditorGroup !== 'areas') {
            return;
        }

        const rect = canvas.getBoundingClientRect();
        const screenX = event.clientX - rect.left;
        const screenY = event.clientY - rect.top;
        const nextIndex = areaIndexAtCanvasPoint(screenX, screenY);

        state.activeAreaIndex = nextIndex;
        buildAreasEditor();
        render();
    });

    canvas.addEventListener('dblclick', () => {
        state.scale = state.fitScale;
        state.offsetX = state.fitOffsetX;
        state.offsetY = state.fitOffsetY;
        render();
    });

    labelsToggle.addEventListener('change', () => {
        state.showLabels = labelsToggle.checked;
        syncChangesInput();
        render();
    });

    resetButton?.addEventListener('click', resetToBase);
    window.addEventListener('resize', resizeCanvas);

    updateStats();
    syncChangesInput();
    buildEditor();
    buildAreasEditor();
    resizeCanvas();
}

document.querySelectorAll('[data-adirs-viewer]').forEach(initAdirsViewer);
