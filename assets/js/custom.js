const searchToggle = document.getElementById('site-search-toggle');
const searchPanel = document.getElementById('site-search-panel');
const searchInput = document.getElementById('site-search-query');

if (searchToggle && searchPanel && searchInput) {
    searchToggle.addEventListener('click', () => {
        searchPanel.hidden = !searchPanel.hidden;
        searchToggle.setAttribute('aria-expanded', String(!searchPanel.hidden));
        if (!searchPanel.hidden) searchInput.focus();
    });

    searchPanel.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            searchPanel.hidden = true;
            searchToggle.setAttribute('aria-expanded', 'false');
            searchToggle.focus();
        }
    });
}
