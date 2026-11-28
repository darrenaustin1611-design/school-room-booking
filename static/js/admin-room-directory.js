(() => {
    const directory = document.querySelector('[data-room-directory]');
    if (!directory) return;
    const search = directory.querySelector('#admin-room-search');
    const status = directory.querySelector('#admin-room-results');
    const clear = directory.querySelector('[data-clear-room-search]');
    const empty = directory.querySelector('[data-room-empty]');
    const groups = [...directory.querySelectorAll('[data-room-category]')];
    const normalize = value => value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const entries = groups.map(group => ({
        group,
        count: group.querySelector('[data-room-count]'),
        rows: [...group.querySelectorAll('[data-room-row]')].map(row => ({ row, text: normalize(row.dataset.roomSearch) }))
    }));
    let searching = false;
    let previousOpen = null;

    // Normal browsing opens one category. Search expands all matching categories.
    groups.forEach(group => group.addEventListener('toggle', () => {
        if (searching || !group.open) return;
        groups.forEach(other => { if (other !== group) other.open = false; });
    }));

    function filterRooms() {
        const query = normalize(search.value.trim());
        const terms = query.split(/\s+/).filter(Boolean);
        if (query && !searching) previousOpen = groups.find(group => group.open) || null;
        searching = Boolean(query);
        let total = 0;
        entries.forEach(({ group, count, rows }) => {
            let matches = 0;
            rows.forEach(({ row, text }) => {
                row.hidden = !terms.every(term => text.includes(term));
                if (!row.hidden) matches++;
            });
            total += matches;
            count.textContent = searching ? `${matches} / ${rows.length}` : rows.length;
            group.hidden = searching && matches === 0;
            group.open = searching ? matches > 0 : group === previousOpen;
        });
        clear.hidden = !searching;
        empty.hidden = !searching || total > 0;
        status.textContent = searching
            ? `${total} ${total === 1 ? 'room' : 'rooms'} found. Matching categories are expanded.`
            : 'Choose a category to view its rooms.';
    }
    search.addEventListener('input', filterRooms);
    clear.addEventListener('click', () => {
        search.value = '';
        filterRooms();
        search.focus();
    });
    if (search.value) filterRooms();
})();
