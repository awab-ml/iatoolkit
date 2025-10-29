document.addEventListener('DOMContentLoaded', function() {
    const reloadButton = document.getElementById('force-reload-button');
    if (!reloadButton) return;

    const originalIconClass = 'bi bi-arrow-clockwise';
    const spinnerIconClass = 'spinner-border spinner-border-sm';

    // Configuración de Toastr para que aparezca abajo a la derecha
    toastr.options = { "positionClass": "toast-bottom-right", "preventDuplicates": true };

    reloadButton.addEventListener('click', async function(event) {
        event.preventDefault();

        if (reloadButton.disabled) return; // Prevenir doble clic

        // 1. Deshabilitar y mostrar spinner
        reloadButton.disabled = true;
        const icon = reloadButton.querySelector('i');
        icon.className = spinnerIconClass;
        toastr.info('Iniciando recarga de contexto en segundo plano...');

        try {
            // 2. Definir los parámetros para callToolkit
            const apiPath = '/api/init-context';
            const payload = { 'user_identifier': window.user_identifier };

            // 3. Hacer la llamada usando callToolkit
            const data = await callToolkit(apiPath, payload, 'POST');

            // 4. Procesar la respuesta
            // callToolkit devuelve null si hubo un error que ya mostró en el chat.
            if (data) {
                if (data.status === 'OK') {
                    toastr.success(data.message || 'Contexto recargado exitosamente.');
                } else {
                    // El servidor respondió 200 OK pero con un mensaje de error en el cuerpo
                    toastr.error(data.error_message || 'Ocurrió un error desconocido durante la recarga.');
                }
            } else {
                // Si data es null, callToolkit ya manejó el error (mostrando un mensaje en el chat).
                // Añadimos un toast para notificar al usuario que algo falló.
                toastr.error('Falló la recarga del contexto. Revisa el chat para más detalles.');
            }
        } catch (error) {
            // Este bloque se ejecutará para errores no controlados por callToolkit (como AbortError)
            console.error('Error durante la recarga del contexto:', error);
            toastr.error(error.message || 'Error de red al intentar recargar.');
        } finally {
            // 5. Restaurar el botón en cualquier caso
            reloadButton.disabled = false;
            icon.className = originalIconClass;
        }
    });
});