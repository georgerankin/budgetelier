// static/inline_edit.js
// Claude assisted me in figuring out how to structure these functions for modularity's sake.

function enableEdit(rowEl) {
    rowEl.querySelectorAll('.display-cell, .display-actions')
        .forEach(el => el.style.display = 'none');
    rowEl.querySelectorAll('.edit-cell:not(.edit-hidden)')
        .forEach(el => el.style.display = 'table-cell');
    rowEl.querySelectorAll('.edit-actions')
        .forEach(el => el.style.display = 'inline-block');
}

function cancelEdit(rowEl) {
    rowEl.querySelectorAll('.edit-cell, .edit-actions')
        .forEach(el => el.style.display = 'none');
    rowEl.querySelectorAll('.display-cell')
        .forEach(el => el.style.display = 'table-cell');
    rowEl.querySelectorAll('.display-actions')
        .forEach(el => el.style.display = 'inline-block');
}

async function saveEdit(rowEl, endpoint) {
    // Collect all named inputs/selects inside edit-cells
    const formData = new FormData();
    rowEl.querySelectorAll('.edit-cell [name]').forEach(input => {
        formData.append(input.name, input.value);
    });

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });
        if (response.ok) {
            location.reload()
        } else {
            const errorText = await reponse.text();
            alert('could not save changes. Server said: \n\n' + errorText);
        }

    } catch (err) {
        console.error('Network error during saveEdit:', err);
        alert('A network error occured. Please check you connection');
    }
}
