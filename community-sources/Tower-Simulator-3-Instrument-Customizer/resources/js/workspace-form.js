function initWorkspaceForm(root) {
    const optionsNode = root.querySelector('[data-workspace-options]');
    const airports = optionsNode ? JSON.parse(optionsNode.textContent || '[]') : [];
    const airportSelect = root.querySelector('[data-workspace-airport]');
    const databaseSelect = root.querySelector('[data-workspace-database]');
    const setSelect = root.querySelector('[data-workspace-set]');
    const summary = root.querySelector('[data-workspace-summary]');

    let preferredDatabase = databaseSelect.getAttribute('data-selected') || databaseSelect.value;
    let preferredSet = setSelect.getAttribute('data-selected') || setSelect.value;

    if (!airportSelect.value && airports.length > 0) {
        airportSelect.value = String(airports[0].id);
    }

    function setOptions(select, values, preferredValue, formatLabel) {
        select.innerHTML = '';
        select.disabled = values.length === 0;

        if (values.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'No options available';
            select.append(option);
            return;
        }

        values.forEach((value, index) => {
            const option = document.createElement('option');
            option.value = String(value.id);
            option.textContent = formatLabel(value);
            option.selected = String(preferredValue) === String(value.id) || (!preferredValue && index === 0);
            select.append(option);
        });
    }

    function renderSummary(airport) {
        if (!airport) {
            summary.textContent = 'Select an airport to see which database variants and instrument sets are available.';
            return;
        }

        const activeSet = airport.instrument_sets.find((set) => String(set.id) === setSelect.value);
        const screenLabel = activeSet && activeSet.screens.length > 0
            ? activeSet.screens.join(', ')
            : 'no screens detected';

        summary.textContent = `${airport.code} has ${airport.database_variants.length} database variant(s) and ${airport.instrument_sets.length} instrument set(s). Selected set covers ${screenLabel}.`;
    }

    function syncForAirport() {
        const airport = airports.find((entry) => String(entry.id) === airportSelect.value);

        if (!airport) {
            setOptions(databaseSelect, [], '', (value) => value.name);
            setOptions(setSelect, [], '', (value) => value.name);
            renderSummary(null);
            return;
        }

        setOptions(databaseSelect, airport.database_variants, preferredDatabase, (value) => value.name);
        setOptions(setSelect, airport.instrument_sets, preferredSet, (value) => value.name);
        preferredDatabase = databaseSelect.value;
        preferredSet = setSelect.value;
        renderSummary(airport);
    }

    airportSelect.addEventListener('change', syncForAirport);
    databaseSelect.addEventListener('change', () => {
        preferredDatabase = databaseSelect.value;
        syncForAirport();
    });
    setSelect.addEventListener('change', () => {
        preferredSet = setSelect.value;
        syncForAirport();
    });

    syncForAirport();
}

document.querySelectorAll('[data-workspace-form]').forEach(initWorkspaceForm);
