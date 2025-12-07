document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const previewContainer = document.getElementById('previewContainer');
    const imagePreview = document.getElementById('imagePreview');
    const removeBtn = document.getElementById('removeBtn');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const dropZoneContent = document.querySelector('.drop-zone-content');

    // Form fields
    const formFields = {
        name: document.getElementById('name'),
        category: document.getElementById('category'),
        description: document.getElementById('description'),
        location: document.getElementById('location'),
        date: document.getElementById('date')
    };

    // Default category
    if (formFields.category && !formFields.category.value) {
        formFields.category.value = 'Dokumenty';
    }

    // Drag & Drop handlers
    dropZone.addEventListener('click', (e) => {
        // Avoid double file picker when clicking directly on the hidden input
        if (e.target === fileInput) return;
        fileInput.click();
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--primary)';
        dropZone.style.background = 'rgba(79, 70, 229, 0.1)';
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.style.borderColor = 'var(--border)';
        dropZone.style.background = 'transparent';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--border)';
        dropZone.style.background = 'transparent';

        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleFile(fileInput.files[0]);
        }
    });

    removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        resetUpload();
    });

    function handleFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('Proszę przesłać plik obrazu.');
            return;
        }

        // Show preview
        const reader = new FileReader();
        reader.onload = (e) => {
            imagePreview.src = e.target.result;
            previewContainer.hidden = false;
            previewContainer.style.display = 'block';
            dropZoneContent.hidden = true;
            if (removeBtn) removeBtn.style.display = 'inline-block';
        };
        reader.readAsDataURL(file);

        // Upload and Analyze
        uploadAndAnalyze(file);
    }

    function resetUpload() {
        fileInput.value = '';
        previewContainer.hidden = true;
        previewContainer.style.display = 'none';
        dropZoneContent.hidden = false;
        imagePreview.src = '';
        if (removeBtn) removeBtn.style.display = 'none';
    }

    async function uploadAndAnalyze(file) {
        loadingOverlay.hidden = false;

        const formData = new FormData();
        formData.append('image', file);

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                populateForm(result.data);
            } else {
                console.error('Analysis failed:', result);
            }
        } catch (error) {
            console.error('Error uploading file:', error);
        } finally {
            loadingOverlay.hidden = true;
        }
    }

    function populateForm(data) {
        // Animate fields being filled
        if (data.name) formFields.name.value = data.name;
        if (data.category) formFields.category.value = data.category;
        if (data.description) formFields.description.value = data.description;
        if (data.location) formFields.location.value = data.location;
        if (data.date) formFields.date.value = data.date;

        // Highlight the form to show it was updated
        const formCard = document.querySelector('.form-card');
        formCard.style.boxShadow = '0 0 0 2px var(--primary)';
        setTimeout(() => {
            formCard.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.2)';
        }, 1000);
    }

    // Handle Form Submission
    const form = document.getElementById('lostItemForm');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const submitBtn = form.querySelector('.submit-btn');
        const originalBtnText = submitBtn.innerText;
        submitBtn.innerText = 'Wysyłanie...';
        submitBtn.disabled = true;

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch('/report', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                // Show success state
                submitBtn.innerText = 'Sukces! ✓';
                submitBtn.style.background = 'linear-gradient(135deg, #10b981, #059669)';

                showToast('Przedmiot zgłoszony pomyślnie! Powiadomimy Cię, gdy ktoś o niego zapyta.', '✅');

                setTimeout(() => {
                    form.reset();
                    resetUpload();
                    submitBtn.innerText = originalBtnText;
                    submitBtn.style.background = ''; // Reset to CSS default
                    submitBtn.disabled = false;
                }, 2000);
            } else {
                showToast('Błąd: ' + result.error, '❌');
                submitBtn.innerText = originalBtnText;
                submitBtn.disabled = false;
            }
        } catch (error) {
            console.error('Error submitting form:', error);
            showToast('Wystąpił błąd. Spróbuj ponownie.', '⚠️');
            submitBtn.innerText = originalBtnText;
            submitBtn.disabled = false;
        }
    });

    function showToast(message, icon = 'ℹ️') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.innerHTML = `
            <span class="toast-icon">${icon}</span>
            <span class="toast-message">${message}</span>
        `;

        container.appendChild(toast);

        // Trigger animation
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });

        // Auto dismiss
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                toast.remove();
            }, 300); // Wait for transition to finish
        }, 5000);
    }
});

// Claim Modal Logic
const claimModal = document.getElementById('claimModal');
const claimForm = document.getElementById('claimForm');
const modalExamples = document.getElementById('modalExamples');

function openClaimModal(itemId, question, examples) {
    document.getElementById('claimItemId').value = itemId;
    document.getElementById('modalQuestion').innerText = question || "Brak pytania (opisz przedmiot)";
    if (modalExamples) {
        if (Array.isArray(examples) && examples.length) {
            modalExamples.innerHTML = `<div style="font-weight:600; margin-bottom:4px;">Przykładowe poprawne odpowiedzi:</div><ul style="padding-left:18px; margin:0;">${examples.map(e => `<li>${e}</li>`).join('')}</ul>`;
            modalExamples.hidden = false;
        } else {
            modalExamples.innerHTML = '';
            modalExamples.hidden = true;
        }
    }
    claimModal.hidden = false;
}

function closeClaimModal() {
    claimModal.hidden = true;
    claimForm.reset();
}

// Close modal when clicking outside
window.onclick = function (event) {
    if (event.target == claimModal) {
        closeClaimModal();
    }
}

if (claimForm) {
    claimForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const submitBtn = claimForm.querySelector('.submit-btn');
        const originalBtnText = submitBtn.innerText;
        submitBtn.innerText = 'Wysyłanie...';
        submitBtn.disabled = true;

        const itemId = document.getElementById('claimItemId').value;
        const answer = document.getElementById('claimAnswer').value;

        try {
            const response = await fetch('/claim', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ item_id: itemId, answer: answer })
            });

            const result = await response.json();

            if (result.success) {
                closeClaimModal();
                // We need to define showToast globally or attach it to window if script.js is module
                // For now assuming showToast is accessible or we duplicate logic briefly
                // Better: make showToast global
                const container = document.getElementById('toast-container');
                if (container) {
                    // Quick hack to reuse toast logic if not globally exposed
                    // Ideally refactor showToast to be outside DOMContentLoaded or attached to window
                    const toast = document.createElement('div');
                    toast.className = 'toast show';
                    toast.innerHTML = `<span class="toast-icon">✅</span><span class="toast-message">${result.message}</span>`;
                    container.appendChild(toast);
                    setTimeout(() => toast.remove(), 5000);
                } else {
                    alert(result.message);
                }
            }
        } catch (error) {
            console.error('Error claiming item:', error);
            alert('Wystąpił błąd.');
        } finally {
            submitBtn.innerText = originalBtnText;
            submitBtn.disabled = false;
        }
    });
}
