// Global variables for request management
let currentAbortController = null;
let isRequestInProgress = false;

// Global variable for company-specific UI config
let specificDataConfig;


$(document).ready(function () {

    // Get company-specific UI configuration from the window object
    specificDataConfig = window.company_ui_config;

    // --- MAIN EVENT HANDLERS ---
    $('#send-button').on('click', handleChatMessage);
    $('#stop-button').on('click', abortCurrentRequest);


    // --- TEXTAREA FUNCTIONALITY ---
    const questionTextarea = $('#question');

    // Handle Enter key press for sending message
    questionTextarea.on('keypress', function (event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // Prevent new line on Enter
            handleChatMessage();
        }
    });

    // Auto-resize textarea and manage send button state on input
    questionTextarea.on('input', function () {
        autoResizeTextarea(this);
        updateSendButtonState();
    });


    // --- PROMPT ASSISTANT FUNCTIONALITY ---
    // This listener is now attached to '.input-area' which is the correct parent container
    $('.input-area').on('click', '.dropdown-menu a.dropdown-item', function (event) {
        event.preventDefault();
        const selectedPrompt = $(this).data('value');
        const selectedDescription = $(this).text().trim();

        $('#prompt-select-button').text(selectedDescription).addClass('item-selected');
        $('#prompt-select-value').val(selectedPrompt);
        $('#prompt-select-description').val(selectedDescription);
        $('#clear-selection-button').show();

        // Enable the send button as a prompt has been selected
        updateSendButtonState();
    });

    // Handle the clear button for the prompt selector
    $('#clear-selection-button').on('click', function() {
        resetPromptSelect();
        // Update send button state, disabling it if necessary
        updateSendButtonState();
    });


    // --- COMPANY-SPECIFIC DATA INPUT FUNCTIONALITY (if enabled) ---
    if (specificDataConfig && specificDataConfig.enabled) {
        const specificInput = $('#' + specificDataConfig.id);
        const clearSpecificInputButton = $('#clear-' + specificDataConfig.id + '-button');

        specificInput.on('input', function () {
            if ($(this).val().trim() !== '') {
                $(this).addClass('has-content');
                clearSpecificInputButton.show();
            } else {
                $(this).removeClass('has-content');
                clearSpecificInputButton.hide();
            }
        });

        clearSpecificInputButton.on('click', resetSpecificDataInput);
    }

    // Set initial state for the send button (it should be disabled)
    updateSendButtonState();
});


/**
 * Main function to handle sending a chat message.
 */
const handleChatMessage = async function () {
    // Abort if a request is already in progress
    if (isRequestInProgress) {
        abortCurrentRequest();
        return;
    }

    const question = $('#question').val().trim();
    const selectedPrompt = $('#prompt-select-value').val();
    const selectedDescription = $('#prompt-select-description').val();
    let specificDataValue = '';

    // Prevent sending if both inputs are empty (button should be disabled anyway)
    if (!question && !selectedPrompt) {
        return;
    }

    // Get value from company-specific field if it exists
    if (specificDataConfig && specificDataConfig.enabled) {
        specificDataValue = $('#' + specificDataConfig.id).val().trim();
    }

    // Determine what to display in the user's message bubble
    const displayMessage = question || selectedDescription;
    displayUserMessage(displayMessage, selectedDescription, specificDataValue, selectedPrompt);

    showSpinner();
    toggleSendStopButtons(true);

    // Reset all UI elements to their initial state
    $('#question').val('');
    autoResizeTextarea($('#question')[0]); // Reset textarea height
    resetPromptSelect();
    if (specificDataConfig && specificDataConfig.enabled) {
        resetSpecificDataInput();
    }

    // Close the prompt assistant collapse area
    const promptCollapseEl = document.getElementById('prompt-assistant-collapse');
    const promptCollapse = bootstrap.Collapse.getInstance(promptCollapseEl);
    if (promptCollapse) {
        promptCollapse.hide();
    }

    const files = window.filePond.getFiles();
    const filesBase64 = await Promise.all(files.map(fileItem => toBase64(fileItem.file)));

    // Prepare data payload
    const client_data = {
        prompt_name: selectedPrompt,
        question: question,
    };
    if (specificDataConfig && specificDataConfig.enabled && specificDataValue) {
        client_data[specificDataConfig.data_key] = specificDataValue;
    }

    const data = {
        question: question,
        prompt_name: selectedPrompt,
        client_data: client_data,
        files: filesBase64.map(fileData => ({
            filename: fileData.name,
            content: fileData.base64
        })),
        external_user_id: window.externalUserId
    };

    try {
        const responseData = await callLLMAPI("/llm_query", data, "POST");
        if (responseData && responseData.answer) {
            const answerSection = $('<div>').addClass('answer-section llm-output').append(responseData.answer);
            displayBotMessage(answerSection);
        }
        // Example for other use cases like document classification
        if (responseData && responseData.aditional_data && 'classify_documents' in responseData.aditional_data && responseData.aditional_data.classify_documents.length > 0) {
             display_document_validation(responseData.aditional_data.classify_documents);
        }
    } catch (error) {
        console.error("Error in handleChatMessage:", error);
        if (error.name === 'AbortError') {
            const message = window.isManualAbort ? 'Request cancelled by user' : 'Request timed out. Please try again.';
            const alertClass = window.isManualAbort ? 'alert-warning' : 'alert-danger';
            const errorDiv = $('<div>').addClass(`error-section alert ${alertClass}`).append(message);
            displayBotMessage(errorDiv);
            window.isManualAbort = false; // Reset flag
        } else {
            const commError = $('<div>').addClass('error-section alert alert-danger').append(`Connection error: ${error.message}`);
            displayBotMessage(commError);
        }
    } finally {
        hideSpinner();
        toggleSendStopButtons(false);
        updateSendButtonState(); // Re-evaluate send button state
        window.filePond.removeFiles();
    }
};


/**
 * Auto-resizes the textarea to fit its content.
 * @param {HTMLElement} element The textarea element.
 */
function autoResizeTextarea(element) {
    element.style.height = 'auto'; // Temporarily shrink to re-calculate scroll height
    element.style.height = (element.scrollHeight) + 'px';
}

/**
 * Enables or disables the send button based on whether there's content
 * in the textarea or a prompt has been selected.
 */
function updateSendButtonState() {
    const question = $('#question').val().trim();
    const selectedPrompt = $('#prompt-select-value').val();
    const sendButton = $('#send-button');

    if (question || selectedPrompt) {
        sendButton.removeClass('disabled');
    } else {
        sendButton.addClass('disabled');
    }
}


/**
 * Toggles the main action button between 'Send' and 'Stop'.
 * @param {boolean} showStop - If true, shows the Stop button. Otherwise, shows the Send button.
 */
const toggleSendStopButtons = function (showStop) {
    $('#send-button-container').toggle(!showStop);
    $('#stop-button-container').toggle(showStop);
};

/**
 * Resets the prompt selector to its default state.
 */
function resetPromptSelect() {
    $('#prompt-select-button').text('Prompts disponibles ....').removeClass('item-selected');
    $('#prompt-select-value').val('');
    $('#prompt-select-description').val('');
    $('#clear-selection-button').hide();
}

/**
 * Resets the company-specific data input field.
 */
function resetSpecificDataInput() {
    if (specificDataConfig && specificDataConfig.enabled) {
        const input = $('#' + specificDataConfig.id);
        input.val('').removeClass('has-content');
        $('#clear-' + specificDataConfig.id + '-button').hide();
    }
}


/**
 * Generic function to make API calls to the backend.
 * @param {string} apiPath - The API endpoint path.
 * @param {object} data - The data payload to send.
 * @param {string} method - The HTTP method (e.g., 'POST').
 * @param {number} timeoutMs - Timeout in milliseconds.
 * @returns {Promise<object|null>} The response data or null on error.
 */
const callLLMAPI = async function(apiPath, data, method, timeoutMs = 500000) {
    const url = `${window.iatoolkit_base_url}/${window.companyShortName}${apiPath}`;

    const headers = {"Content-Type": "application/json"};
    if (window.sessionJWT) {
        headers['X-Chat-Token'] = window.sessionJWT;
    }

    const controller = new AbortController();
    currentAbortController = controller;
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(url, {
            method: method,
            headers: headers,
            body: JSON.stringify(data),
            signal: controller.signal,
            credentials: 'include'
        });
        clearTimeout(timeoutId);

        if (!response.ok) {
            const errorData = await response.json();
            const endpointError = $('<div>').addClass('error-section').append(`<p>${errorData.error_message || 'Unknown server error'}</p>`);
            displayBotMessage(endpointError);
            return null;
        }
        return await response.json();
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw error; // Re-throw to be handled by handleChatMessage
        } else {
            const commError = $('<div>').addClass('error-section').append(`<p>Connection error: ${error.message}</p>`);
            displayBotMessage(commError);
        }
        return null;
    }
};


/**
 * Displays the user's message in the chat container.
 */
const displayUserMessage = function(question, selectedDescription, specificDataValue, selectedPrompt) {
    const chatContainer = $('#chat-container');
    const userMessage = $('<div>').addClass('message shadow-sm');
    let messageText;
    let isEditable = true;

    if (specificDataValue && question && !selectedPrompt) {
        messageText = $('<span>').text(`${specificDataValue}: ${question}`);
    } else if (specificDataValue && !question && selectedPrompt) {
        messageText = $('<span>').text(`${specificDataValue}: ${selectedDescription}`);
        isEditable = false;
    } else if (!specificDataValue && selectedPrompt) {
        messageText = $('<span>').text(`${selectedDescription}`);
        isEditable = false;
    } else {
        messageText = $('<span>').text(question);
    }

    userMessage.append(messageText);

    if (isEditable && question) {
        const editIcon = $('<i>').addClass('bi bi-pencil-fill edit-icon').attr('title', 'Edit query').on('click', function () {
            $('#question').val(question).focus();
            autoResizeTextarea($('#question')[0]);
            updateSendButtonState();
        });
        userMessage.append(editIcon);
    }
    chatContainer.append(userMessage);
};

/**
 * Appends a message from the bot to the chat container.
 * @param {jQuery} section - The jQuery object to append.
 */
function displayBotMessage(section) {
    const chatContainer = $('#chat-container');
    chatContainer.append(section);
    chatContainer.scrollTop(chatContainer[0].scrollHeight);
}

/**
 * Aborts the current in-progress API request.
 */
const abortCurrentRequest = function () {
    if (currentAbortController && isRequestInProgress) {
        window.isManualAbort = true;
        currentAbortController.abort();
    }
};

/**
 * Shows the loading spinner in the chat.
 */
const showSpinner = function () {
    if ($('#spinner').length) return;
    const accessibilityClass = (typeof bootstrap !== 'undefined') ? 'visually-hidden' : 'sr-only';
    const spinner = $(`
        <div id="spinner" style="display: flex; align-items: center; justify-content: start; margin: 10px 0; padding: 10px;">
            <div class="spinner-border text-primary" role="status" style="width: 1.5rem; height: 1.5rem; margin-right: 15px;">
                <span class="${accessibilityClass}">Loading...</span>
            </div>
            <span style="font-weight: bold; font-size: 15px;">Loading...</span>
        </div>
    `);
    $('#chat-container').append(spinner).scrollTop($('#chat-container')[0].scrollHeight);
};

/**
 * Hides the loading spinner.
 */
function hideSpinner() {
    $('#spinner').fadeOut(function () {
        $(this).remove();
    });
}

/**
 * Converts a File object to a Base64 encoded string.
 * @param {File} file The file to convert.
 * @returns {Promise<{name: string, base64: string}>}
 */
function toBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve({name: file.name, base64: reader.result.split(",")[1]});
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

/**
 * Displays the document validation results.
 * @param {Array<object>} document_list
 */
function display_document_validation(document_list) {
    const requiredFields = ['document_name', 'document_type', 'causes', 'is_valid'];
    for (const doc of document_list) {
        if (!requiredFields.every(field => field in doc)) {
            console.warn("Document with incorrect structure:", doc);
            continue;
        }
        const docValidationSection = $('<div>').addClass('document-section card mt-2 mb-2');
        const cardBody = $('<div>').addClass('card-body');
        const headerDiv = $('<div>').addClass('d-flex justify-content-between align-items-center mb-2');
        const filenameSpan = $(`
                <div>
                    <span class="text-primary fw-bold">File: </span>
                    <span class="text-secondary">${doc.document_name}</span>
                </div>`);
        const badge_style = doc.is_valid ? 'bg-success' : 'bg-danger';
        const documentBadge = $('<span>')
            .addClass(`badge ${badge_style} p-2`)
            .text(doc.document_type);
        headerDiv.append(filenameSpan).append(documentBadge);
        cardBody.append(headerDiv);

        if (!doc.is_valid && doc.causes && doc.causes.length > 0) {
            const rejectionSection = $('<div>').addClass('rejection-reasons mt-2');
            rejectionSection.append('<h6 class="text-danger">Rejection Causes:</h6>');
            const causesList = doc.causes.map(cause => `<li class="text-secondary">${cause}</li>`).join('');
            rejectionSection.append(`<ul class="list-unstyled">${causesList}</ul>`);
            cardBody.append(rejectionSection);
        } else if (doc.is_valid) {
            const validSection = $('<div>').addClass('mt-2');
            validSection.append('<p class="text-success fw-bold">Valid document.</p>');
            cardBody.append(validSection);
        }
        docValidationSection.append(cardBody);
        displayBotMessage(docValidationSection);
    }
}