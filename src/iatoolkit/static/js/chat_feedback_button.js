$(document).ready(function () {
    $('#submit-feedback').on('click', function () {
        sendFeedback(this);
    });

    // Evento para enviar el feedback
    async function sendFeedback(submitButton) {
        toastr.options = {"positionClass": "toast-bottom-right", "preventDuplicates": true};
        const feedbackText = $('#feedback-text').val().trim();
        const activeStars = $('.star.active').length;

        if (!feedbackText) {
            toastr.error('Por favor, escribe tu comentario antes de enviar.');
            return;
        }

        if (activeStars === 0) {
            toastr.error('Por favor, califica al asistente con las estrellas.');
            return;
        }

        submitButton.disabled = true;

        // call the IAToolkit API to send feedback
        const data = {
            "user_identifier": window.user_identifier,
            "message": feedbackText,
            "rating": activeStars,
        };

        const responseData = await callToolkit('/api/feedback', data, "POST");
        if (responseData)
            toastr.success('¡Gracias por tu comentario!', 'Feedback Enviado');
        else
            toastr.error('No se pudo enviar el feedback, por favor intente nuevamente.');

        submitButton.disabled = false;
        $('#feedbackModal').modal('hide');
    }

// Evento para abrir el modal de feedback
$('#send-feedback-button').on('click', function () {
    $('#submit-feedback').prop('disabled', false);
    $('#submit-feedback').html('<i class="bi bi-send me-1 icon-spaced"></i>Enviar');
    $('.star').removeClass('active hover-active'); // Resetea estrellas
    $('#feedback-text').val(''); // Limpia texto
    $('.modal-body .alert').remove(); // Quita alertas previas
    $('#feedbackModal').modal('show');
});

// Evento que se dispara DESPUÉS de que el modal se ha ocultado
$('#feedbackModal').on('hidden.bs.modal', function () {
    $('#feedback-text').val('');
    $('.modal-body .alert').remove();
    $('.star').removeClass('active');
});

// Función para el sistema de estrellas
window.gfg = function (rating) {
    $('.star').removeClass('active');
    $('.star').each(function (index) {
        if (index < rating) {
            $(this).addClass('active');
        }
    });
};

$('.star').hover(
    function () {
        const rating = $(this).data('rating');
        $('.star').removeClass('hover-active');
        $('.star').each(function (index) {
            if ($(this).data('rating') <= rating) {
                $(this).addClass('hover-active');
            }
        });
    },
    function () {
        $('.star').removeClass('hover-active');
    });

});
