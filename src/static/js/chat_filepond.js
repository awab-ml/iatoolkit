$(document).ready(function () {
    const paperclipButton = $('#paperclip-button');
    const viewFilesButtonContainer = $('#view-files-button-container');
    const viewFilesButton = $('#view-files-button');
    const uploadedFilesModalElement = $('#uploadedFilesModal');
    const uploadedFilesModal = uploadedFilesModalElement;  // En Bootstrap 3, el elemento jQuery es el modal
    const uploadedFilesList = $('#uploaded-files-list');

    // Initialize FilePond
    window.filePond = FilePond.create(
        document.querySelector('#file-upload'), {
        allowMultiple: true,
        labelIdle: '',
        credits: false,
        allowFileSizeValidation: true,
        maxFileSize: '10MB',
        stylePanelLayout: null,
        itemInsertLocation: 'after',
        instantUpload: false,
    });

    $('.filepond--root').hide(); // Ocultar la UI de FilePond

    // Función para actualizar la visibilidad del icono "ver archivos"
    function updateFileIconsVisibility() {
        const files = filePond.getFiles();
        if (files.length > 0) {
            viewFilesButtonContainer.show();
        } else {
            viewFilesButtonContainer.hide();
            if (uploadedFilesModalElement.hasClass('in')) { // Si el modal está abierto y no hay archivos, ciérralo
                uploadedFilesModal.modal('hide');
            }
        }
    }

    // Función para poblar el modal con los archivos y botones de eliminar
    function populateFilesModal() {
        uploadedFilesList.empty(); // Limpiar lista anterior
        const files = filePond.getFiles();

        if (files.length === 0) {
            uploadedFilesList.append('<li class="list-group-item">No hay archivos adjuntos.</li>');
            return;
        }

        files.forEach(file => {
            const listItem = $(`
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    <span class="file-name-modal">${file.filename}</span>
                    <button type="button" class="btn btn-sm btn-outline-danger remove-file-btn" data-file-id="${file.id}" title="Eliminar archivo">
                        <i class="bi bi-trash-fill"></i>
                    </button>
                </li>
            `);
            uploadedFilesList.append(listItem);
        });
    }

        // Event listeners de FilePond
    window.filePond.on('addfile', () => updateFileIconsVisibility());
    window.filePond.on('removefile', () => {
        updateFileIconsVisibility();
        if (uploadedFilesModalElement.hasClass('in')) {
            populateFilesModal();
        }
    });

    // Event listeners de los botones de la UI
    paperclipButton.on('click', () => window.filePond.browse());
    viewFilesButton.on('click', () => {
        populateFilesModal();
        uploadedFilesModal.modal('show');
    });
    uploadedFilesList.on('click', '.remove-file-btn', function () {
        const fileIdToRemove = $(this).data('file-id');
        if (fileIdToRemove) {
            window.filePond.removeFile(fileIdToRemove);
        }
    });

    // Inicializar visibilidad al cargar
    updateFileIconsVisibility();
});

