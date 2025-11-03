$(document).ready(function () {
    $('#force-reload-button').on('click', function() {
        reloadButton(this);
     });

    async function reloadButton(button) {
        const originalIconClass = 'bi bi-arrow-clockwise';
        const spinnerIconClass = 'spinner-border spinner-border-sm';

        // Configuración de Toastr para que aparezca abajo a la derecha
        toastr.options = {"positionClass": "toast-bottom-right", "preventDuplicates": true};

        // 1. Deshabilitar y mostrar spinner
        button.disabled = true;
        const icon = button.querySelector('i');
        icon.className = spinnerIconClass;
        toastr.info('Iniciando recarga de contexto en segundo plano...');

        // 2. prepare the api parameters
        const apiPath = '/api/init-context';
        const payload = {'user_identifier': window.user_identifier};

        // 3. make the call to callToolkit
        const data = await callToolkit(apiPath, payload, 'POST');
        if (data) {
            if (data.status === 'OK')
                toastr.success(data.message || 'Contexto recargado.');
            else
                toastr.error(data.error_message || 'Ocurrió un error desconocido durante la recarga.');
        }

        button.disabled = false;
        icon.className = originalIconClass;
    }
});