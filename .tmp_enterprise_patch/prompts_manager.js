/**
 * PromptsManagerModule
 * Visual editor for Prompt Management (Jinja templates + Metadata JSON).
 */
const PromptsManagerModule = {
    moduleId: 'prompts_manager',
    companyShortName: null,
    userRole: '',
    companyRuntimeMode: 'static',
    isHostedCompany: false,
    readOnlyMode: false,
    readOnlyReason: null,

    // State
    promptsTree: {}, // Cached structure
    currentPrompt: null, // { name, category, ... }
    isDirty: false, // Track unsaved changes
    playgroundPond: null,
    playgroundPollTimer: null,
    playgroundTaskId: null,
    playgroundLastOutputHtml: '',
    playgroundLastStructuredOutput: null,
    editors: {
        content: null, // CodeMirror instance for text
        outputSchema: null, // CodeMirror instance for output schema YAML
    },

    // API Endpoints
    endpoints: {
        list: null,
        detail: null, // Dynamic: /api/prompts/<name>
        execute: null, // Dynamic: /api/prompts/<name>/execute
        tasks: null,
    },

    // Cache for categories options (Local cache populated from Shell)
    optionsCache: {
        types: [],
        categories: [],
        models: []
    },
    supportedPromptTypes: ['company', 'agent'],

    t: function(key, fallback, params) {
        let value = (typeof t_js === 'function') ? t_js(key) : key;
        if (!value || value === key) value = fallback || key;

        if (params && typeof value === 'string') {
            Object.keys(params).forEach((name) => {
                const token = `{${name}}`;
                value = value.split(token).join(String(params[name]));
            });
        }
        return value;
    },

    initTooltips: function() {
        if (typeof bootstrap === 'undefined' || !bootstrap.Tooltip) return;
        const elements = document.querySelectorAll('#module-prompts_manager [data-bs-toggle="tooltip"]');
        elements.forEach((el) => {
            bootstrap.Tooltip.getOrCreateInstance(el);
        });
    },

    /**
     * Initialization
     */
    init: function() {
        console.log("[PromptsManager] Initializing...");
        const module = document.getElementById('module-prompts_manager');
        if (module) module.classList.remove('d-none');

        if (!window.IAT_CONFIG) {
            console.error("❌ [PromptsManager] IAT_CONFIG missing!");
            return;
        }
        this.companyShortName = window.IAT_CONFIG.companyShortName;
        this.userRole = String(window.IAT_CONFIG.userRole || '').trim().toLowerCase();
        this.companyRuntimeMode = String(window.IAT_CONFIG.companyRuntimeMode || 'static').trim().toLowerCase();
        this.isHostedCompany = this.companyRuntimeMode === 'hosted';

        const hasEditRole = (this.userRole === 'admin' || this.userRole === 'owner');
        this.readOnlyMode = this.isHostedCompany || !hasEditRole;
        this.readOnlyReason = this.isHostedCompany ? 'hosted' : (!hasEditRole ? 'role' : null);

        // API Setup
        const apiBase = `/${this.companyShortName}/api/prompts`;
        this.endpoints.list = apiBase;
        this.endpoints.execute = `/${this.companyShortName}/api/llm_query`;
        this.endpoints.tasks = `/${this.companyShortName}/api/tasks`;

        // Setup UI
        this.initEditors();
        this.applyReadOnlyMode();
        this.initPlaygroundFilePond();

        // Load categories options from DashboardShell
        this.loadOptionsFromShell()

        this.loadPromptsList();

        this.bindEvents();
        this.initTooltips();
        this.clearPlaygroundOutputCopy();
    },

    destroy: function() {
        this.stopPlaygroundPolling();
        this.clearPlaygroundOutputCopy();
        if (this.playgroundPond) {
            this.playgroundPond.destroy();
            this.playgroundPond = null;
        }
    },

    // Bridge to DashboardShell
    loadOptionsFromShell: function() {
        if (typeof DashboardShell === 'undefined') return Promise.resolve();

        return DashboardShell.loadSharedMetadata().then(meta => {
            const metaTypes = Array.isArray(meta.prompt_types) ? meta.prompt_types : [];
            const normalizedTypes = metaTypes
                .map((value) => String(value || '').trim().toLowerCase())
                .filter((value, index, array) => value && array.indexOf(value) === index);
            const allowedTypes = normalizedTypes.filter((value) => this.supportedPromptTypes.includes(value));

            this.optionsCache.types = allowedTypes.length > 0
                ? allowedTypes
                : [...this.supportedPromptTypes];
            this.optionsCache.categories = meta.prompt_categories || [];
            this.optionsCache.models = meta.llm_models || [];
            this.populateSelectors();
        });
    },

    getReadOnlyMessage: function() {
        const localeCode = String((window.IAT_LOCALE && window.IAT_LOCALE.code) || '').toLowerCase();
        const isSpanish = localeCode.startsWith('es');

        if (this.readOnlyReason === 'hosted') {
            return isSpanish
                ? 'La edición de prompts está deshabilitada para empresas hosted.'
                : 'Prompt editing is disabled for hosted companies.';
        }
        return isSpanish
            ? 'La edición de prompts requiere rol admin u owner.'
            : 'Prompt editing requires admin or owner role.';
    },

    notifyReadOnly: function() {
        if (window.toastr) toastr.warning(this.getReadOnlyMessage());
    },

    isEditable: function() {
        return !this.readOnlyMode;
    },

    setConfigInputsDisabled: function(disabled) {
        const ids = [
            'config-description',
            'config-category',
            'config-active',
            'config-output-type',
            'config-output-schema-mode',
            'config-output-response-mode',
            'config-attachment-mode',
            'config-attachment-fallback',
        ];
        ids.forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.disabled = Boolean(disabled);
        });

        const fieldsContainer = document.getElementById('config-fields-container');
        if (!fieldsContainer) {
            this.applyOutputTypeUI();
            return;
        }

        fieldsContainer.querySelectorAll('input, select, button, textarea').forEach((el) => {
            el.disabled = Boolean(disabled);
        });

        fieldsContainer.querySelectorAll('i[onclick]').forEach((el) => {
            if (disabled) {
                el.classList.add('text-muted');
                el.style.pointerEvents = 'none';
            } else {
                el.classList.remove('text-muted');
                el.style.pointerEvents = '';
            }
        });

        this.applyOutputTypeUI();
    },

    applyReadOnlyMode: function() {
        const isReadOnly = this.readOnlyMode;

        const banner = document.getElementById('prompts-readonly-banner');
        if (banner) {
            if (isReadOnly) {
                banner.classList.remove('d-none');
                banner.innerHTML = `<i class="bi bi-lock-fill me-2"></i>${this.getReadOnlyMessage()}`;
            } else {
                banner.classList.add('d-none');
                banner.textContent = '';
            }
        }

        ['btn-new-prompt', 'btn-save-prompt', 'btn-delete-prompt', 'btn-create-prompt']
            .forEach((id) => {
                const btn = document.getElementById(id);
                if (!btn) return;
                btn.disabled = isReadOnly;
                btn.classList.toggle('disabled', isReadOnly);
            });

        ['link-manage-prompt-categories', 'link-add-prompt-variable'].forEach((id) => {
            const link = document.getElementById(id);
            if (!link) return;
            link.classList.toggle('disabled', isReadOnly);
            link.setAttribute('aria-disabled', isReadOnly ? 'true' : 'false');
            link.style.pointerEvents = isReadOnly ? 'none' : '';
            link.style.opacity = isReadOnly ? '0.6' : '';
        });

        if (this.editors.content) {
            this.editors.content.setOption('readOnly', isReadOnly ? 'nocursor' : false);
        }
        if (this.editors.outputSchema) {
            this.editors.outputSchema.setOption('readOnly', isReadOnly ? 'nocursor' : false);
        }
        this.setConfigInputsDisabled(isReadOnly);
    },

    inferOutputTypeFromMeta: function(meta) {
        if (!meta || typeof meta !== 'object') return 'free_text';

        const yamlText = typeof meta.output_schema_yaml === 'string'
            ? meta.output_schema_yaml.trim()
            : '';
        if (yamlText) return 'structured_json';

        if (meta.output_schema && typeof meta.output_schema === 'object' && !Array.isArray(meta.output_schema)) {
            return 'structured_json';
        }
        return 'free_text';
    },

    getOutputSchemaYamlFromMeta: function(meta) {
        if (!meta || typeof meta !== 'object') return '';

        if (typeof meta.output_schema_yaml === 'string') {
            return meta.output_schema_yaml;
        }

        const schemaObj = meta.output_schema;
        if (schemaObj && typeof schemaObj === 'object' && !Array.isArray(schemaObj)) {
            if (typeof jsyaml !== 'undefined') {
                return jsyaml.dump(schemaObj, { indent: 2, lineWidth: -1, noRefs: true });
            }
            return JSON.stringify(schemaObj, null, 2);
        }

        return '';
    },

    setOutputSchemaStatus: function(level, message) {
        const status = document.getElementById('output-schema-yaml-status');
        if (!status) return;

        status.className = 'badge';
        if (level === 'ok') status.classList.add('bg-success-subtle', 'text-success-emphasis', 'border', 'border-success-subtle');
        else if (level === 'error') status.classList.add('bg-danger-subtle', 'text-danger-emphasis', 'border', 'border-danger-subtle');
        else status.classList.add('bg-secondary-subtle', 'text-secondary-emphasis', 'border', 'border-secondary-subtle');

        status.textContent = message;
    },

    getOutputTypeSelection: function() {
        const outputTypeEl = document.getElementById('config-output-type');
        return ((outputTypeEl && outputTypeEl.value) || 'free_text').toString().trim().toLowerCase();
    },

    applyOutputTypeUI: function() {
        const outputType = this.getOutputTypeSelection();
        const structuredEnabled = outputType === 'structured_json';
        const schemaMode = document.getElementById('config-output-schema-mode');
        const responseMode = document.getElementById('config-output-response-mode');
        const disabledHint = document.getElementById('output-schema-disabled-hint');

        if (schemaMode) schemaMode.disabled = this.readOnlyMode || !structuredEnabled;
        if (responseMode) responseMode.disabled = this.readOnlyMode || !structuredEnabled;

        if (disabledHint) {
            disabledHint.classList.toggle('d-none', structuredEnabled);
        }

        if (this.editors.outputSchema) {
            const readOnly = this.readOnlyMode;
            this.editors.outputSchema.setOption('readOnly', readOnly ? 'nocursor' : false);
        }

        if (!structuredEnabled) {
            this.setOutputSchemaStatus('muted', this.t('prompts_schema_status_disabled', 'Inactive (free text)'));
            return;
        }

        this.validateOutputSchemaYaml({ silent: true });
    },

    validateOutputSchemaYaml: function(options = {}) {
        const silent = Boolean(options.silent);
        const forceRequired = Boolean(options.forceRequired);
        const structuredEnabled = this.getOutputTypeSelection() === 'structured_json';
        const yamlText = this.editors.outputSchema ? this.editors.outputSchema.getValue() : '';

        if (!structuredEnabled && !forceRequired) {
            this.setOutputSchemaStatus('muted', this.t('prompts_schema_status_disabled', 'Inactive (free text)'));
            return { valid: true, yaml: '' };
        }

        if (!yamlText || !yamlText.trim()) {
            const message = this.t('prompts_schema_yaml_required', 'Output schema YAML is required.');
            this.setOutputSchemaStatus('error', this.t('prompts_schema_status_yaml_required', 'YAML required'));
            if (!silent && window.toastr) toastr.error(message);
            return { valid: false, message };
        }

        if (typeof jsyaml === 'undefined') {
            const message = this.t('prompts_schema_yaml_parser_missing', 'Missing dependency: js-yaml.');
            this.setOutputSchemaStatus('error', this.t('prompts_schema_status_parser_missing', 'YAML parser missing'));
            if (!silent && window.toastr) toastr.error(message);
            return { valid: false, message };
        }

        try {
            const parsed = jsyaml.load(yamlText);
            if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
                throw new Error(this.t('prompts_schema_root_object_required', 'Schema root must be an object.'));
            }

            this.setOutputSchemaStatus('ok', this.t('prompts_schema_status_valid', 'Valid YAML'));
            return { valid: true, yaml: yamlText };
        } catch (err) {
            const reason = err.message || this.t('prompts_invalid_yaml_format', 'Invalid YAML format.');
            const message = this.t(
                'prompts_schema_invalid_with_reason',
                'Invalid output schema YAML: {message}',
                {message: reason}
            );
            this.setOutputSchemaStatus('error', this.t('prompts_schema_status_invalid', 'Invalid YAML'));
            if (!silent && window.toastr) toastr.error(message);
            return { valid: false, message: reason };
        }
    },

    /**
     * Initialize CodeMirror instances
     */
    initEditors: function() {
        // 1. Content Editor (Jinja2 / Markdown-like)
        const contentArea = document.getElementById('editor-content-wrapper');
        if (contentArea && !this.editors.content) {
            this.editors.content = CodeMirror(contentArea, {
                mode: "jinja2",
                lineNumbers: true,
                theme: "default",
                lineWrapping: true,
                viewportMargin: Infinity
            });

            // Track changes in CodeMirror
            this.editors.content.on('change', (cm, change) => {
                if (change.origin !== 'setValue') {
                    this.markDirty();
                }
            });

            // Auto-refresh when tab becomes visible
            this.editors.content.setSize("100%", "100%");
        }

        // 2. Output Schema Editor (YAML)
        const outputSchemaArea = document.getElementById('editor-output-schema-wrapper');
        if (outputSchemaArea && !this.editors.outputSchema) {
            this.editors.outputSchema = CodeMirror(outputSchemaArea, {
                mode: "yaml",
                lineNumbers: true,
                theme: "default",
                lineWrapping: true,
                viewportMargin: Infinity
            });

            this.editors.outputSchema.on('change', (cm, change) => {
                if (change.origin !== 'setValue') {
                    this.markDirty();
                }
                this.validateOutputSchemaYaml({ silent: true });
            });

            this.resizeOutputSchemaEditor();
        }
    },

    resizeOutputSchemaEditor: function() {
        if (!this.editors.outputSchema) return;

        const wrapper = document.getElementById('editor-output-schema-wrapper');
        if (wrapper) {
            const height = wrapper.clientHeight;
            if (height > 0) {
                this.editors.outputSchema.setSize('100%', `${height}px`);
            } else {
                this.editors.outputSchema.setSize('100%', '100%');
            }
        } else {
            this.editors.outputSchema.setSize('100%', '100%');
        }

        this.editors.outputSchema.refresh();
    },

    bindEvents: function() {
        // Search & Type Filter Logic (Unified)
        const searchInput = document.getElementById('prompt-search-input');
        const typeFilter = document.getElementById('prompt-filter-type');

        const applyFilters = () => {
            const term = searchInput ? searchInput.value.toLowerCase() : '';
            const typeVal = typeFilter ? typeFilter.value.toLowerCase() : 'all';

            // Filter Items
            document.querySelectorAll('.prompt-tree-item').forEach(el => {
                const text = el.textContent.toLowerCase();
                const itemType = el.getAttribute('data-prompt-type') || 'company';

                // Logic: Match Text AND (Type is All OR Type Matches)
                const matchesText = text.includes(term);
                const matchesType = (typeVal === 'all') || (itemType === typeVal);

                el.style.display = (matchesText && matchesType) ? 'block' : 'none';
            });

            // Filter Categories (Hide header if all children are hidden)
            document.querySelectorAll('.category-header').forEach(header => {
                let hasVisibleChildren = false;
                let sibling = header.nextElementSibling;

                // Iterate siblings until next header or end
                while (sibling && !sibling.classList.contains('category-header')) {
                    if (sibling.style.display !== 'none') {
                        hasVisibleChildren = true;
                    }
                    sibling = sibling.nextElementSibling;
                }

                header.style.display = hasVisibleChildren ? 'block' : 'none';
            });
        };

        if (searchInput) searchInput.addEventListener('input', applyFilters);
        if (typeFilter) typeFilter.addEventListener('change', applyFilters);

        // Intercept Tab Switching (e.g., going to Playground)
        const moduleContainer = document.getElementById('module-prompts_manager');
        if (moduleContainer) {
            const tabs = moduleContainer.querySelectorAll('button[data-bs-toggle="tab"]');
            tabs.forEach(tab => {
                tab.addEventListener('show.bs.tab', (e) => {
                    if (this.isDirty) {
                        e.preventDefault(); // Stop navigation
                        this.showUnsavedAlert(() => {
                            this.resetDirty();
                            // Manually show the tab after confirmation
                            const tabTrigger = new bootstrap.Tab(e.target);
                            tabTrigger.show();
                        });
                    }
                });
            });
        }

        // Fix CodeMirror refresh on Tab switch
        const tabEditor = document.getElementById('tab-editor');
        if (tabEditor) {
            tabEditor.addEventListener('shown.bs.tab', () => {
                if (this.editors.content) this.editors.content.refresh();
            });
        }

        const tabOutput = document.getElementById('tab-output');
        if (tabOutput) {
            tabOutput.addEventListener('shown.bs.tab', () => {
                setTimeout(() => this.resizeOutputSchemaEditor(), 50);
            });
        }

        window.addEventListener('resize', () => {
            this.resizeOutputSchemaEditor();
        });

        // --- METADATA INPUTS CHANGE TRACKING ---
        const descInput = document.getElementById('config-description');
        if (descInput) descInput.addEventListener('input', () => this.markDirty());

        const activeCheck = document.getElementById('config-active');
        if (activeCheck) activeCheck.addEventListener('change', () => this.markDirty());

        const catSelect = document.getElementById('config-category');
        if (catSelect) catSelect.addEventListener('change', () => this.markDirty());

        const outputTypeSelect = document.getElementById('config-output-type');
        if (outputTypeSelect) {
            outputTypeSelect.addEventListener('change', () => {
                this.applyOutputTypeUI();
                this.markDirty();
            });
        }

        const outputSchemaModeSelect = document.getElementById('config-output-schema-mode');
        if (outputSchemaModeSelect) outputSchemaModeSelect.addEventListener('change', () => this.markDirty());

        const outputResponseModeSelect = document.getElementById('config-output-response-mode');
        if (outputResponseModeSelect) outputResponseModeSelect.addEventListener('change', () => this.markDirty());

        const attachmentModeSelect = document.getElementById('config-attachment-mode');
        if (attachmentModeSelect) attachmentModeSelect.addEventListener('change', () => this.markDirty());

        const attachmentFallbackSelect = document.getElementById('config-attachment-fallback');
        if (attachmentFallbackSelect) attachmentFallbackSelect.addEventListener('change', () => this.markDirty());


        // --- DELETE MODAL BINDING ---
        const btnConfirmDelete = document.getElementById('btn-prompt-confirm-delete');
        if (btnConfirmDelete) {
            // Clone to ensure no duplicate listeners if re-initialized
            const newBtn = btnConfirmDelete.cloneNode(true);
            btnConfirmDelete.parentNode.replaceChild(newBtn, btnConfirmDelete);

            newBtn.addEventListener('click', () => {
                this.executeDelete();
            });
        }

        // --- CATEGORY UPDATE LISTENER ---
        // Listen for global updates from DashboardShell
        $(document).on('categoriesUpdated', (e, key) => {
            if (key === 'prompt_categories') {
                console.log("[PromptsManager] Categories updated externally, reloading...");
                this.loadOptionsFromShell(); // This will fetch new metadata and call populateSelectors()
            }
        });

        this.applyOutputTypeUI();

    },

    // --- DATA LOADING ---
    loadPromptsList: function() {
        const container = document.getElementById('prompts-list-container');
        if (!container) return;

        // Spinner
        container.innerHTML = `
                <div class="text-center mt-5 text-muted small">
                    <div class="spinner-border spinner-border-sm mb-2"></div>
                    <div>${this.t('prompts_refreshing_library', 'Refreshing library...')}</div>
                </div>
            `;

        fetch(`${this.endpoints.list}?all=true`)
            .then(res => res.json())
            .then(data => {
                this.renderTree(data);
            })
            .catch(err => {
                console.error("Error loading prompts:", err);
                container.innerHTML = `<div class="p-3 text-danger small">Error: ${err.message}</div>`;
            });
    },

    renderTree: function(data) {
        const container = document.getElementById('prompts-list-container');
        container.innerHTML = '';

        // Prepare categories for Datalist (New Prompt Modal)
        const dataList = document.getElementById('category-options');
        if (dataList) dataList.innerHTML = '';

        // Handle the specific structure: { message: [ {category_name:..., prompts: []} ] }
        let categories = [];
        if (data && Array.isArray(data.message)) {
            categories = data.message;
        } else if (Array.isArray(data)) {
             // Fallback if the API returns the array directly
            categories = data;
        }

        if (categories.length === 0) {
            container.innerHTML = `<div class="p-3 text-muted text-center small">${this.t('prompts_no_prompts_found', 'No prompts found. Create one!')}</div>`;
            return;
        }

        // Sort categories by order if available
        categories.sort((a, b) => (a.category_order || 0) - (b.category_order || 0));

        categories.forEach(catObj => {
            const catName = catObj.category_name || 'Uncategorized';
            const prompts = catObj.prompts || [];

            // Populate datalist
            if (dataList) {
                const opt = document.createElement('option');
                opt.value = catName;
                dataList.appendChild(opt);
            }

            // Render Category Header
            const catHeader = document.createElement('div');
            catHeader.className = 'category-header bg-light px-3 py-1 border-bottom border-top small fw-bold text-uppercase text-muted mt-2';
            catHeader.textContent = catName;
            container.appendChild(catHeader);

            // Sort prompts by order inside category
            prompts.sort((a, b) => (a.order || 0) - (b.order || 0));

            // Render Prompt Items
            if (prompts.length === 0) {
                const emptyItem = document.createElement('div');
                emptyItem.className = 'px-3 py-2 small text-muted fst-italic';
                emptyItem.textContent = this.t('prompts_no_prompts', 'No prompts');
                container.appendChild(emptyItem);
            } else {
                prompts.forEach(p => {
                    const pName = p.prompt; // The API uses 'prompt' key for the name
                    const pDesc = p.description || '';

                    // Determine Type for Icon & Filter
                    // API might return 'type', 'prompt_type' or nothing (default company)
                    const rawType = p.type || p.prompt_type || 'company';
                    const pType = rawType.toLowerCase();

                    // Icon Class Logic
                    let iconClass = 'type-icon-default';
                    if (pType === 'company') iconClass = 'type-icon-company';
                    else if (pType === 'agent') iconClass = 'type-icon-agent';

                    const item = document.createElement('div');
                    item.className = 'prompt-tree-item list-group-item list-group-item-action py-2 border-0 small';

                    // Store type for filtering
                    item.setAttribute('data-prompt-type', pType);

                    // FIX: Re-apply active class if this is the current prompt
                    if (this.currentPrompt && this.currentPrompt.name === pName) {
                        item.classList.add('active');
                    }

                    // Added dynamic class to <i>
                    item.innerHTML = `
                            <div class="d-flex align-items-center justify-content-between">
                                <span class="text-truncate">
                                    <i class="bi bi-file-text-fill me-2 ${iconClass}" title="${pType}"></i>${pName}
                                </span>
                                ${pDesc ? '<i class="bi bi-info-circle-fill text-muted opacity-25" style="font-size: 0.7em;"></i>' : ''}
                            </div>
                        `;
                    item.onclick = () => this.selectPrompt(catName, pName, item, pType);
                    container.appendChild(item);
                });
            }
        });

        // Apply current filters after render (in case we are refreshing and a filter is set)
        const typeFilter = document.getElementById('prompt-filter-type');
        if (typeFilter) {
            // Trigger change event manually or call apply logic if extracted
            const event = new Event('change');
            typeFilter.dispatchEvent(event);
        }
    },

    // --- SELECTION & EDITING ---

    selectPrompt: function(category, name, domElement, promptType = null) {

        // Check for unsaved changes before switching
        if (this.isDirty) {
            this.showUnsavedAlert(() => {
                this.resetDirty(); // Clear dirty state
                this.selectPrompt(category, name, domElement, promptType); // Retry selection
            });
            return;
        }

        // UI Highlight
        document.querySelectorAll('.prompt-tree-item').forEach(el => el.classList.remove('active'));
        if (domElement) domElement.classList.add('active');

        this.currentPrompt = { category, name, type: promptType };

        // Update Headers
        document.getElementById('current-prompt-name').textContent = name;
        document.getElementById('current-prompt-category').textContent = category;

        // Reset Type Badge temporarily
        const typeBadge = document.getElementById('current-prompt-type-badge');
        if (typeBadge) {
            typeBadge.textContent = '';
            typeBadge.style.visibility = 'hidden';
        }

        // Show Workspace, Hide Placeholder
        document.getElementById('workspace-container').style.setProperty('display', 'flex', 'important');
        document.getElementById('workspace-placeholder').classList.add('d-none');
        document.getElementById('prompt-actions-toolbar').style.visibility = 'visible';

        // Refresh CodeMirror when workspace becomes visible to fix gutter alignment
        if (this.editors.content) {
            setTimeout(() => this.editors.content.refresh(), 50);
            }

        // Load Detail
        this.loadPromptDetail(name);
    },

    loadPromptDetail: function(name) {
        // Loading state
        if (this.editors.content) this.editors.content.setValue(this.t('loading', 'Loading...'));

        // Reset Dirty State immediately to avoid false positives during load
        this.resetDirty();

        // Clear GUI (Safety check added)
        const descInput = document.getElementById('config-description');
        if (descInput) descInput.value = '';

        // FIX: Corregido el ID para coincidir con la estructura Side Drawer
        const fieldsContainer = document.getElementById('config-fields-container');
        if (fieldsContainer) fieldsContainer.innerHTML = '';

        const url = `${this.endpoints.list}/${name}`;

        fetch(url)
            .then(res => res.json())
            .then(data => {
                // 1. Set Content
                if (this.editors.content) {
                    this.editors.content.setValue(data.content || "");
                }

                // 2. Set GUI Config
                this.renderConfigUI(data.meta || {});

                // 3. Update Type Badge (New location, no colors)
                const meta = data.meta || {};

                // FIX: Look for 'type' as well, since API might return it that way
                const promptType = meta.type || meta.prompt_type || data.type || data.prompt_type || '';

                const typeBadge = document.getElementById('current-prompt-type-badge');

                // Critical: Update currentPrompt state
                if (this.currentPrompt) {
                    this.currentPrompt.type = promptType;
                }

                // Reset dirty again after all values are set (including CodeMirror setValue)
                this.resetDirty();

                if (typeBadge && promptType) {
                    typeBadge.textContent = promptType; // e.g. "company"
                    typeBadge.style.visibility = 'visible';

                    // Style update for badges using Custom CSS classes
                    const pTypeLower = promptType.toLowerCase();

                    // Reset base classes
                    typeBadge.className = 'badge fw-normal';

                    if (pTypeLower === 'agent') {
                        typeBadge.classList.add('badge-type-agent');
                    } else if (pTypeLower === 'company') {
                        typeBadge.classList.add('badge-type-company');
                    }
                }


                // Reset Playground Tab if active
                const playgroundOutput = document.getElementById('playground-output');
                if (playgroundOutput) {
                    playgroundOutput.innerHTML = `<div class="h-100 d-flex align-items-center justify-content-center text-muted opacity-50"><p>${this.t('prompts_run_prompt_to_see_results', 'Run the prompt to see results.')}</p></div>`;
                }
                this.stopPlaygroundPolling();
                this.resetPlaygroundAttachments();
                document.getElementById('metric-latency').textContent = '-';
                document.getElementById('metric-tokens').textContent = '-';
                this.clearPlaygroundOutputCopy();
                this.clearPlaygroundStructuredOutput();

                // If user is already on Playground tab, refresh inputs immediately
                const tabPlayground = document.getElementById('tab-playground');
                if (tabPlayground && tabPlayground.classList.contains('active')) {
                    this.preparePlayground();
                }

            })
            .catch(err => {
                console.error("Load Detail Error:", err);
                if (window.toastr) toastr.error(this.t('prompts_failed_to_load_details', 'Failed to load prompt details'));
            });
    },

    /**
     * Renders the Visual Configuration Editor (Side Panel)
     */
    renderConfigUI: function(meta) {

        // 0. Set Active State (Read from static HTML widget)
        const activeCheckbox = document.getElementById('config-active');
        if (activeCheckbox) {
            // Default to true if undefined, otherwise use the value
            activeCheckbox.checked = meta.active !== false;
        }

        // 1. Description
        const descInput = document.getElementById('config-description');
        if (descInput) descInput.value = meta.description || '';

        // 2. Category Selection (Robust Case-Insensitive Match)
        const catSelect = document.getElementById('config-category');
        if (catSelect) {
            // Default to placeholder
            catSelect.value = "";

            // Try to match specific category
            const targetCategory = (meta.category || (this.currentPrompt ? this.currentPrompt.category : '')).toString().toLowerCase();

            if (targetCategory) {
                Array.from(catSelect.options).forEach(opt => {
                    if (opt.value.toLowerCase() === targetCategory) {
                        catSelect.value = opt.value;
                    }
                });
            }
        }

        // 3. Output Behavior
        const outputType = this.inferOutputTypeFromMeta(meta);
        const outputTypeSelect = document.getElementById('config-output-type');
        if (outputTypeSelect) outputTypeSelect.value = outputType;

        const schemaMode = String(meta.output_schema_mode || 'best_effort').trim().toLowerCase();
        const schemaModeSelect = document.getElementById('config-output-schema-mode');
        if (schemaModeSelect) {
            schemaModeSelect.value = (schemaMode === 'strict') ? 'strict' : 'best_effort';
        }

        const responseMode = String(meta.output_response_mode || 'chat_compatible').trim().toLowerCase();
        const responseModeSelect = document.getElementById('config-output-response-mode');
        if (responseModeSelect) {
            responseModeSelect.value = (responseMode === 'structured_only') ? 'structured_only' : 'chat_compatible';
        }

        const attachmentMode = String(meta.attachment_mode || 'extracted_only').trim().toLowerCase();
        const attachmentModeSelect = document.getElementById('config-attachment-mode');
        if (attachmentModeSelect) {
            const allowedModes = ['extracted_only', 'native_only', 'native_plus_extracted', 'auto'];
            attachmentModeSelect.value = allowedModes.includes(attachmentMode) ? attachmentMode : 'extracted_only';
        }

        const attachmentFallback = String(meta.attachment_fallback || 'extract').trim().toLowerCase();
        const attachmentFallbackSelect = document.getElementById('config-attachment-fallback');
        if (attachmentFallbackSelect) {
            attachmentFallbackSelect.value = (attachmentFallback === 'fail') ? 'fail' : 'extract';
        }

        const schemaYaml = this.getOutputSchemaYamlFromMeta(meta);
        if (this.editors.outputSchema) {
            this.editors.outputSchema.setValue(schemaYaml || '');
            setTimeout(() => this.resizeOutputSchemaEditor(), 0);
        }
        this.applyOutputTypeUI();

        // 4. Custom Fields List
        const container = document.getElementById('config-fields-container');
        const emptyMsg = document.getElementById('config-fields-empty');
        if (!container) return;

        container.innerHTML = '';
        const fields = meta.custom_fields || [];

        if (fields.length === 0) {
            if (emptyMsg) emptyMsg.classList.remove('d-none');
        } else {
            if (emptyMsg) emptyMsg.classList.add('d-none');
            fields.forEach(field => {
                this.addCustomFieldRow(field);
            });
        }

        this.setConfigInputsDisabled(this.readOnlyMode);
    },

    /**
     * Adds a card item to the custom fields list (Side Drawer Style)
     */
    addCustomFieldRow: function(fieldData = {}) {
        const container = document.getElementById('config-fields-container');
        const emptyMsg = document.getElementById('config-fields-empty');

        if (!container) return; // Safety check
        if (emptyMsg) emptyMsg.classList.add('d-none');

        // Default values
        const key = fieldData.data_key || '';
        const label = fieldData.label || '';
        const type = fieldData.type || 'text';

        // Create a compact card for the field
        const row = document.createElement('div');
        row.className = 'card shadow-sm border p-2 config-field-item mb-2';
        row.innerHTML = `
                <div class="mb-2">
                    <label class="form-label small text-muted mb-0 fw-bold" style="font-size: 0.7rem;">Jinja Variable (data_key)</label>
                    <div class="d-flex justify-content-between align-items-center">
                        <input type="text" class="form-control form-control-sm font-monospace text-primary border-0 p-0 field-key fw-bold" 
                               style="font-size: 0.85rem; background: #f8f9fa; padding: 2px 5px !important;"
                               placeholder="e.g. client_name" value="${key}">
                        
                        <div class="d-flex align-items-center gap-1 ms-2">
                            <!-- Ordering Controls -->
                            <button class="btn btn-sm btn-link text-secondary p-0" onclick="PromptsManagerModule.moveField(this, -1)" title="Move Up">
                                <i class="bi bi-arrow-up-short"></i>
                            </button>
                            <button class="btn btn-sm btn-link text-secondary p-0" onclick="PromptsManagerModule.moveField(this, 1)" title="Move Down">
                                <i class="bi bi-arrow-down-short"></i>
                            </button>
                            <div class="vr mx-1"></div>
                            <i class="bi bi-x text-danger" style="cursor: pointer;" onclick="PromptsManagerModule.removeField(this)" title="Remove"></i>
                        </div>
                    </div>
                </div>
            
            <div class="row g-2">
                <div class="col-7">
                     <label class="form-label small text-muted mb-0" style="font-size: 0.7rem;">Label</label>
                     <input type="text" class="form-control form-control-sm field-label" 
                       placeholder="User friendly label" value="${label}">
                </div>
                <div class="col-5">
                    <label class="form-label small text-muted mb-0" style="font-size: 0.7rem;">Type</label>
                    <select class="form-select form-select-sm field-type py-0" style="font-size: 0.8rem;">
                        <option value="text" ${type === 'text' ? 'selected' : ''}>Text</option>
                        <option value="textarea" ${type === 'textarea' ? 'selected' : ''}>Long Text</option>
                        <option value="number" ${type === 'number' ? 'selected' : ''}>Number</option>
                        <option value="date" ${type === 'date' ? 'selected' : ''}>Date</option>
                        <option value="boolean" ${type === 'boolean' ? 'selected' : ''}>Boolean</option>
                    </select>
                </div>
            </div>
        `;

        container.appendChild(row);
    },

    addCustomField: function() {
        if (!this.isEditable()) {
            this.notifyReadOnly();
            return;
        }
        this.addCustomFieldRow();
        this.setConfigInputsDisabled(this.readOnlyMode);
    },

    /**
     * Reorders field items in the DOM
     * @param {HTMLElement} btn - The button clicked
     * @param {number} direction - -1 for Up, 1 for Down
     */
    moveField: function(btn, direction) {
        if (!this.isEditable()) {
            this.notifyReadOnly();
            return;
        }
        const row = btn.closest('.config-field-item');
        const container = document.getElementById('config-fields-container');

        if (!row || !container) return;

        if (direction === -1) {
            // Move Up
            if (row.previousElementSibling) {
                container.insertBefore(row, row.previousElementSibling);
                this.markDirty();
            }
        } else {
            // Move Down
            if (row.nextElementSibling) {
                // insertBefore with nextSibling's nextSibling effectively inserts after the next sibling
                container.insertBefore(row, row.nextElementSibling.nextElementSibling);
                this.markDirty();
            }
        }
    },

    /**
     * Removes a field item
     */
    removeField: function(btn) {
        if (!this.isEditable()) {
            this.notifyReadOnly();
            return;
        }
        const row = btn.closest('.config-field-item');
        if (row) {
            row.remove();
            this.markDirty();

            // Check if empty to show placeholder
            const container = document.getElementById('config-fields-container');
            const emptyMsg = document.getElementById('config-fields-empty');
            if (container && container.children.length === 0 && emptyMsg) {
                emptyMsg.classList.remove('d-none');
            }
        }
    },

    savePrompt: function() {
        if (!this.isEditable()) {
            this.notifyReadOnly();
            return;
        }
        if (!this.currentPrompt) return;

        const btn = document.getElementById('btn-save-prompt');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

        try {
            // 1. Get Content
            const content = this.editors.content.getValue();

            // 2. Metadata: Description & Active
            const description = document.getElementById('config-description').value.trim();

            // Get Category directly from Settings tab controls.
            const catSelect = document.getElementById('config-category');
            let category = this.currentPrompt.category; // Default to existing

            if (catSelect) {
                // Solo usamos el valor del selector si no está vacío (para evitar borrarlo por error de carga)
                // O si el usuario explícitamente seleccionó el placeholder (que no debería ocurrir si es required)
                if (catSelect.value) {
                    category = catSelect.value;
                }
            }

            // Get Active State directly from the HTML widget
            const activeCheckbox = document.getElementById('config-active');
            const isActive = activeCheckbox ? activeCheckbox.checked : true;

            // 3. Custom Fields - Robust Scraping
            const customFields = [];
            const container = document.getElementById('config-fields-container');

            if (container) {
                const rows = container.getElementsByClassName('config-field-item');

                Array.from(rows).forEach(row => {
                    const keyInput = row.querySelector('.field-key');
                    const labelInput = row.querySelector('.field-label');
                    const typeInput = row.querySelector('.field-type');

                    // Only add if key exists and is not empty
                    if (keyInput && keyInput.value.trim()) {
                        customFields.push({
                            data_key: keyInput.value.trim(),
                            label: labelInput ? labelInput.value.trim() : keyInput.value.trim(),
                            type: typeInput ? typeInput.value : 'text'
                        });
                    }
                });
            }

            const outputType = this.getOutputTypeSelection();
            const useStructuredOutput = outputType === 'structured_json';
            const schemaValidation = this.validateOutputSchemaYaml({ forceRequired: useStructuredOutput, silent: false });
            if (!schemaValidation.valid) {
                throw new Error(schemaValidation.message || 'Invalid output schema YAML.');
            }

            const outputSchemaModeInput = document.getElementById('config-output-schema-mode');
            const outputResponseModeInput = document.getElementById('config-output-response-mode');
            const outputSchemaMode = useStructuredOutput
                ? String((outputSchemaModeInput && outputSchemaModeInput.value) || 'best_effort').trim().toLowerCase()
                : 'best_effort';
            const outputResponseMode = useStructuredOutput
                ? String((outputResponseModeInput && outputResponseModeInput.value) || 'chat_compatible').trim().toLowerCase()
                : 'chat_compatible';
            const attachmentModeInput = document.getElementById('config-attachment-mode');
            const attachmentFallbackInput = document.getElementById('config-attachment-fallback');
            const attachmentMode = String((attachmentModeInput && attachmentModeInput.value) || 'extracted_only').trim().toLowerCase();
            const attachmentFallback = String((attachmentFallbackInput && attachmentFallbackInput.value) || 'extract').trim().toLowerCase();

            // 4. Construct Payload
            const payload = {
                content: content,
                description: description,
                category: category,
                prompt_type: this.currentPrompt.type || 'company',
                active: isActive,
                order: 1,
                custom_fields: customFields,
                output_schema_yaml: useStructuredOutput ? schemaValidation.yaml : '',
                output_schema_mode: outputSchemaMode,
                output_response_mode: outputResponseMode,
                attachment_mode: attachmentMode,
                attachment_fallback: attachmentFallback,
            };

            const url = `${this.endpoints.list}/${this.currentPrompt.name}`;

            fetch(url, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(res => {
                    if (!res.ok) {
                        return res.json().then(errData => {
                            throw new Error(errData.message || errData.error_message || "Save failed");
                        });
                    }
                    return res.json();
                })
                .then(data => {
                    if (data.status === 'error') {
                        throw new Error(data.message);
                    }
                    if (window.toastr) toastr.success(this.t('prompts_saved_ok', 'Prompt saved successfully'));
                    this.resetDirty();
                })
                .catch(err => {
                    console.error("Save Error:", err);
                    if (window.toastr) toastr.error(err.message);
                    btn.innerHTML = `<i class="bi bi-save me-1"></i> ${this.t('prompts_save_btn', 'Save')} *`;

                })
                .finally(() => {
                    btn.disabled = false;
                });

        } catch (err) {
            console.error("Logic Error:", err);
            btn.disabled = false;
            btn.innerHTML = `<i class="bi bi-save me-1"></i> ${this.t('prompts_save_btn', 'Save')} *`; // Restore dirty state text
            if (window.toastr) toastr.error(err.message);
        }

        },


    // --- PLAYGROUND LOGIC ---

    initPlaygroundFilePond: function() {
        const inputElement = document.getElementById('playground-filepond-input');
        if (!inputElement || typeof FilePond === 'undefined') {
            return;
        }

        if (this.playgroundPond) {
            this.playgroundPond.destroy();
            this.playgroundPond = null;
        }

        if (typeof FilePondPluginFileValidateType !== 'undefined') {
            FilePond.registerPlugin(FilePondPluginFileValidateType);
        }
        if (typeof FilePondPluginFileEncode !== 'undefined') {
            FilePond.registerPlugin(FilePondPluginFileEncode);
        }

        this.playgroundPond = FilePond.create(inputElement, {
            allowMultiple: true,
            allowReorder: true,
            instantUpload: false,
            storeAsFile: false,
            credits: false,
            acceptedFileTypes: [
                'application/pdf',
                'text/plain',
                'text/markdown',
                'application/json',
                'text/csv',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'image/png',
                'image/jpeg',
                'image/jpg',
                'image/webp'
            ],
            labelIdle: 'Drop files or <span class="filepond--label-action">Browse</span>'
        });
    },

    setPlaygroundCopyEnabled: function(enabled) {
        const copyBtn = document.getElementById('btn-playground-copy');
        if (!copyBtn) return;
        copyBtn.disabled = !enabled;
    },

    setPlaygroundStructuredActionsEnabled: function(enabled) {
        const copyBtn = document.getElementById('btn-playground-copy-structured');
        const downloadBtn = document.getElementById('btn-playground-download-structured');
        if (copyBtn) copyBtn.disabled = !enabled;
        if (downloadBtn) downloadBtn.disabled = !enabled;
    },

    clearPlaygroundOutputCopy: function() {
        this.playgroundLastOutputHtml = '';
        this.setPlaygroundCopyEnabled(false);
    },

    clearPlaygroundStructuredOutput: function() {
        this.playgroundLastStructuredOutput = null;
        this.setPlaygroundStructuredActionsEnabled(false);
    },

    setPlaygroundOutputCopyHtml: function(outputHtml) {
        const html = typeof outputHtml === 'string' ? outputHtml.trim() : '';
        this.playgroundLastOutputHtml = html;
        this.setPlaygroundCopyEnabled(Boolean(html));
    },

    setPlaygroundStructuredOutput: function(value) {
        const normalized = this.normalizeStructuredOutput(value);
        const enabled = !(normalized === null || typeof normalized === 'undefined');
        this.playgroundLastStructuredOutput = enabled ? normalized : null;
        this.setPlaygroundStructuredActionsEnabled(enabled);
    },

    _playgroundHtmlToText: function(html) {
        const tmp = document.createElement('div');
        tmp.innerHTML = html;
        return (tmp.innerText || tmp.textContent || '').trim();
    },

    escapeHtml: function(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

    normalizeStructuredOutput: function(value) {
        if (value === null || typeof value === 'undefined') return null;
        if (typeof value === 'string') {
            const trimmed = value.trim();
            if (!trimmed) return null;
            if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
                try {
                    return JSON.parse(trimmed);
                } catch (err) {
                    return value;
                }
            }
            return value;
        }
        return value;
    },

    isPlainObject: function(value) {
        return Object.prototype.toString.call(value) === '[object Object]';
    },

    getStructuredValueType: function(value) {
        if (value === null) return 'null';
        if (Array.isArray(value)) return 'array';
        return typeof value;
    },

    getStructuredTypeBadge: function(value) {
        const valueType = this.getStructuredValueType(value);
        const map = {
            object: this.t('prompts_structured_type_object', 'Object'),
            array: this.t('prompts_structured_type_array', 'Array'),
            string: this.t('prompts_structured_type_string', 'String'),
            number: this.t('prompts_structured_type_number', 'Number'),
            boolean: this.t('prompts_structured_type_boolean', 'Boolean'),
            null: this.t('prompts_structured_type_null', 'Null'),
        };
        const label = map[valueType] || String(valueType);
        return `<span class="badge bg-info-subtle text-info-emphasis border border-info-subtle">${this.escapeHtml(label)}</span>`;
    },

    formatStructuredCellValue: function(value) {
        const valueType = this.getStructuredValueType(value);
        if (valueType === 'null') return '<span class="badge bg-secondary-subtle text-secondary-emphasis">null</span>';
        if (valueType === 'boolean') return `<span class="badge bg-light text-dark border">${value ? 'true' : 'false'}</span>`;
        if (valueType === 'number') return `<span class="text-primary fw-semibold">${this.escapeHtml(String(value))}</span>`;
        if (valueType === 'string') return this.escapeHtml(value);
        if (valueType === 'array') return `<span class="badge bg-light text-dark border">[${value.length}]</span>`;
        if (valueType === 'object') return '<span class="badge bg-light text-dark border">{...}</span>';
        return this.escapeHtml(String(value));
    },

    formatStructuredJsonPre: function(value) {
        const json = JSON.stringify(value, null, 2);
        return `<pre class="small bg-body-tertiary border rounded p-3 mb-0"><code>${this.escapeHtml(json)}</code></pre>`;
    },

    buildStructuredArrayTableHtml: function(rows) {
        if (!Array.isArray(rows) || rows.length === 0) {
            return `<div class="alert alert-secondary small mb-0">${this.t('prompts_structured_empty_array', 'Empty array')}</div>`;
        }

        const maxRows = 100;
        const visibleRows = rows.slice(0, maxRows);
        const keys = [];
        const keySet = new Set();

        visibleRows.forEach((row) => {
            if (!this.isPlainObject(row)) return;
            Object.keys(row).forEach((key) => {
                if (!keySet.has(key)) {
                    keySet.add(key);
                    keys.push(key);
                }
            });
        });

        if (!keys.length) {
            return this.formatStructuredJsonPre(rows);
        }

        const head = keys.map((key) => `<th class="small text-nowrap">${this.escapeHtml(key)}</th>`).join('');
        const body = visibleRows.map((row) => {
            const cells = keys.map((key) => `<td class="small align-top">${this.formatStructuredCellValue(row[key])}</td>`).join('');
            return `<tr>${cells}</tr>`;
        }).join('');
        const truncated = rows.length > maxRows
            ? `<div class="small text-muted mt-2">${this.t('prompts_structured_rows_truncated', 'Showing first {count} rows.', {count: maxRows})}</div>`
            : '';

        return `
            <div class="table-responsive border rounded">
                <table class="table table-sm table-striped mb-0">
                    <thead class="table-light"><tr>${head}</tr></thead>
                    <tbody>${body}</tbody>
                </table>
            </div>
            ${truncated}
        `;
    },

    buildStructuredTreeHtml: function(value, depth = 0) {
        const maxDepth = 4;
        if (depth >= maxDepth) {
            return `<span class="text-muted small">${this.t('prompts_structured_depth_limit', 'Depth limit reached')}</span>`;
        }

        if (Array.isArray(value)) {
            const maxItems = 20;
            const items = value.slice(0, maxItems).map((item, index) => `
                <li class="mb-1">
                    <span class="text-muted">[${index}]</span>
                    <div class="ms-3">${this.buildStructuredTreeHtml(item, depth + 1)}</div>
                </li>
            `).join('');
            const hidden = value.length - maxItems;
            const more = hidden > 0 ? `<li class="small text-muted">+${hidden} ${this.t('prompts_structured_more_items', 'more items')}</li>` : '';
            return `<ul class="list-unstyled mb-0">${items}${more}</ul>`;
        }

        if (this.isPlainObject(value)) {
            const keys = Object.keys(value);
            const maxKeys = 40;
            const visibleKeys = keys.slice(0, maxKeys);
            const items = visibleKeys.map((key) => `
                <li class="mb-1">
                    <span class="fw-semibold">${this.escapeHtml(key)}:</span>
                    <div class="ms-3">${this.buildStructuredTreeHtml(value[key], depth + 1)}</div>
                </li>
            `).join('');
            const hidden = keys.length - maxKeys;
            const more = hidden > 0 ? `<li class="small text-muted">+${hidden} ${this.t('prompts_structured_more_keys', 'more keys')}</li>` : '';
            return `<ul class="list-unstyled mb-0">${items}${more}</ul>`;
        }

        return `<span>${this.formatStructuredCellValue(value)}</span>`;
    },

    buildStructuredOutputPaneHtml: function(value) {
        if (Array.isArray(value) && value.length > 0 && value.every((row) => this.isPlainObject(row))) {
            return `
                ${this.buildStructuredArrayTableHtml(value)}
                <div class="mt-3">${this.formatStructuredJsonPre(value)}</div>
            `;
        }

        if (Array.isArray(value) || this.isPlainObject(value)) {
            return `
                <div class="border rounded p-3 mb-3 bg-white">
                    ${this.buildStructuredTreeHtml(value)}
                </div>
                ${this.formatStructuredJsonPre(value)}
            `;
        }

        return `
            <div class="border rounded p-3 bg-white">
                <div class="fs-6">${this.formatStructuredCellValue(value)}</div>
            </div>
            <div class="mt-3">${this.formatStructuredJsonPre(value)}</div>
        `;
    },

    bindPlaygroundResultTabs: function(outputDiv) {
        if (!outputDiv) return;
        const buttons = outputDiv.querySelectorAll('[data-playground-result-tab]');
        const panes = outputDiv.querySelectorAll('[data-playground-result-pane]');
        if (!buttons.length || !panes.length) return;

        buttons.forEach((button) => {
            button.addEventListener('click', () => {
                const tab = button.getAttribute('data-playground-result-tab');
                buttons.forEach((btn) => {
                    const active = btn === button;
                    btn.classList.toggle('active', active);
                    btn.classList.toggle('btn-secondary', active);
                    btn.classList.toggle('btn-outline-secondary', !active);
                });
                panes.forEach((pane) => {
                    const paneName = pane.getAttribute('data-playground-result-pane');
                    pane.classList.toggle('d-none', paneName !== tab);
                });
            });
        });
    },

    renderPlaygroundResult: function(answerHtml, structuredOutput) {
        const outputDiv = document.getElementById('playground-output');
        if (!outputDiv) return;

        const answer = (answerHtml || '').trim() || '(Empty response)';
        const normalized = this.normalizeStructuredOutput(structuredOutput);
        const hasStructured = !(normalized === null || typeof normalized === 'undefined');

        const structuredPane = hasStructured
            ? this.buildStructuredOutputPaneHtml(normalized)
            : `<div class="alert alert-secondary small mb-0">${this.t('prompts_structured_not_available', 'No structured output available in this response.')}</div>`;

        const renderTabClass = hasStructured ? 'btn btn-sm btn-outline-secondary' : 'btn btn-sm btn-secondary active';
        const structuredTabClass = hasStructured ? 'btn btn-sm btn-secondary active' : 'btn btn-sm btn-outline-secondary';
        const renderPaneHidden = hasStructured ? 'd-none' : '';
        const structuredPaneHidden = hasStructured ? '' : 'd-none';
        outputDiv.innerHTML = `
            <div class="d-flex flex-column h-100">
                <div class="playground-result-header mb-3">
                    <div class="playground-result-switch btn-group btn-group-sm" role="tablist" aria-label="Playground result mode">
                        <button type="button" class="${renderTabClass} px-3" data-playground-result-tab="rendered">${this.t('prompts_result_tab_rendered', 'Rendered')}</button>
                        <button type="button" class="${structuredTabClass} px-3" data-playground-result-tab="structured">${this.t('prompts_result_tab_structured', 'Structured')}</button>
                    </div>
                </div>
                <div data-playground-result-pane="rendered" class="${renderPaneHidden}">
                    <div class="answer-section llm-output">${answer}</div>
                </div>
                <div data-playground-result-pane="structured" class="${structuredPaneHidden}">
                    ${structuredPane}
                </div>
            </div>
        `;

        this.setPlaygroundOutputCopyHtml(answer);
        this.setPlaygroundStructuredOutput(normalized);
        this.bindPlaygroundResultTabs(outputDiv);
    },

    copyPlaygroundOutputHtml: async function() {
        const html = (this.playgroundLastOutputHtml || '').trim();
        if (!html) {
            if (window.toastr) toastr.warning(this.t('prompts_no_output_to_copy', 'No playground output available to copy.'));
            return;
        }

        const htmlBlob = new Blob([html], { type: 'text/html' });
        const plainText = this._playgroundHtmlToText(html);

        try {
            if (navigator.clipboard && typeof ClipboardItem !== 'undefined') {
                const clipboardItem = new ClipboardItem({
                    'text/html': htmlBlob,
                    'text/plain': new Blob([plainText], { type: 'text/plain' }),
                });
                await navigator.clipboard.write([clipboardItem]);
                if (window.toastr) toastr.success(this.t('prompts_output_html_copied', 'Output HTML copied to clipboard.'));
                return;
            }

            if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
                await navigator.clipboard.writeText(plainText || html);
                if (window.toastr) toastr.success(this.t('prompts_output_copied', 'Output copied to clipboard.'));
                return;
            }

            throw new Error('Clipboard API is not supported in this browser.');
        } catch (err) {
            if (err && err.name === 'AbortError') {
                return;
            }
            console.error('Could not copy playground output:', err);
            if (window.toastr) {
                toastr.error(this.t(
                    'prompts_output_copy_failed',
                    'Could not copy output: {message}',
                    {message: err.message || this.t('unknown_server_error', 'Unknown error')}
                ));
            }
        }
    },

    copyPlaygroundStructuredOutput: async function() {
        if (this.playgroundLastStructuredOutput === null || typeof this.playgroundLastStructuredOutput === 'undefined') {
            if (window.toastr) toastr.warning(this.t('prompts_no_structured_output_to_copy', 'No structured output available to copy.'));
            return;
        }

        try {
            const json = JSON.stringify(this.playgroundLastStructuredOutput, null, 2);
            await navigator.clipboard.writeText(json);
            if (window.toastr) toastr.success(this.t('prompts_structured_output_copied', 'Structured JSON copied to clipboard.'));
        } catch (err) {
            console.error('Could not copy structured output:', err);
            if (window.toastr) {
                toastr.error(this.t(
                    'prompts_output_copy_failed',
                    'Could not copy output: {message}',
                    {message: err.message || this.t('unknown_server_error', 'Unknown error')}
                ));
            }
        }
    },

    downloadPlaygroundStructuredOutput: function() {
        if (this.playgroundLastStructuredOutput === null || typeof this.playgroundLastStructuredOutput === 'undefined') {
            if (window.toastr) toastr.warning(this.t('prompts_no_structured_output_to_download', 'No structured output available to download.'));
            return;
        }

        try {
            const json = JSON.stringify(this.playgroundLastStructuredOutput, null, 2);
            const blob = new Blob([json], { type: 'application/json' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'structured_output.json';
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Could not download structured output:', err);
            if (window.toastr) {
                toastr.error(this.t(
                    'prompts_output_download_failed',
                    'Could not download output: {message}',
                    {message: err.message || this.t('unknown_server_error', 'Unknown error')}
                ));
            }
        }
    },

    stopPlaygroundPolling: function() {
        if (this.playgroundPollTimer) {
            clearTimeout(this.playgroundPollTimer);
            this.playgroundPollTimer = null;
        }
        this.playgroundTaskId = null;
        this.setPlaygroundRunState(false);
    },

    resetPlaygroundAttachments: function() {
        if (this.playgroundPond) {
            this.playgroundPond.removeFiles();
            return;
        }
        const input = document.getElementById('playground-filepond-input');
        if (input) input.value = '';
    },

    setPlaygroundRunState: function(isRunning) {
        const btn = document.getElementById('btn-playground-run');
        if (!btn) return;

        if (!btn.dataset.defaultHtml) {
            btn.dataset.defaultHtml = btn.innerHTML;
        }

        if (isRunning) {
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>${this.t('prompts_running', 'Running...')}`;
            return;
        }

        btn.disabled = false;
        btn.innerHTML = btn.dataset.defaultHtml;
    },

    formatPlaygroundLatencySeconds: function(startTime) {
        const elapsedMs = Math.max(0, performance.now() - startTime);
        return (elapsedMs / 1000).toFixed(2);
    },

    renderPlaygroundAsyncWaiting: function(taskId, attempt = 0) {
        const outputDiv = document.getElementById('playground-output');
        if (!outputDiv) return;

        const pollLabel = attempt > 0
            ? this.t('prompts_polling_attempt', 'Polling attempt {attempt}', {attempt})
            : this.t('prompts_polling_started', 'Polling started');
        outputDiv.innerHTML = `
            <div class="h-100 d-flex align-items-center justify-content-center text-muted">
                <div class="text-center">
                    <div class="spinner-border text-primary mb-3" role="status" aria-hidden="true"></div>
                    <p class="mb-2">${this.t(
                        'prompts_task_queued_waiting',
                        'Task #{id} queued. Waiting for execution result...',
                        {id: taskId}
                    )}</p>
                    <button type="button" class="btn btn-sm btn-outline-secondary" disabled>
                        <span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>
                        ${this.t('prompts_refreshing_status', 'Refreshing status...')}
                    </button>
                    <div class="small text-secondary mt-2">${pollLabel}</div>
                </div>
            </div>
        `;
    },

    readFileAsDataURL: function(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(new Error(`Could not encode file: ${file.name}`));
            reader.readAsDataURL(file);
        });
    },

    collectPlaygroundFiles: async function() {
        if (!this.playgroundPond) {
            return [];
        }

        const pondFiles = this.playgroundPond.getFiles();
        if (!pondFiles || pondFiles.length === 0) {
            return [];
        }

        return Promise.all(pondFiles.map(async (item) => {
            const file = item.file;
            let content = null;

            if (typeof item.getFileEncodeDataURL === 'function') {
                content = item.getFileEncodeDataURL();
            }
            if (!content) {
                content = await this.readFileAsDataURL(file);
            }

            return {
                filename: file.name,
                content,
                type: file.type || 'application/octet-stream'
            };
        }));
    },

    isCurrentPromptAgent: function() {
        const type = ((this.currentPrompt && this.currentPrompt.type) || '').toString().toLowerCase().trim();
        return type === 'agent';
    },

    updatePlaygroundFilesStatus: function(mainText, subText = '') {
        if (!this.playgroundPond || !this.playgroundPond.element) {
            return;
        }

        const root = this.playgroundPond.element;
        root.querySelectorAll('.filepond--file-status-main').forEach(node => {
            node.textContent = mainText;
        });
        root.querySelectorAll('.filepond--file-status-sub').forEach(node => {
            node.textContent = subText;
        });
    },

    setPlaygroundFilesVisualState: function(state) {
        if (!this.playgroundPond || !this.playgroundPond.element) {
            return;
        }

        const root = this.playgroundPond.element;
        const stateClasses = [
            'playground-file-pending',
            'playground-file-queued',
            'playground-file-sent',
            'playground-file-failed'
        ];

        root.querySelectorAll('.filepond--file').forEach(node => {
            node.classList.remove(...stateClasses);
            if (state) {
                node.classList.add(`playground-file-${state}`);
            }
        });

        root.querySelectorAll('.filepond--file-info-sub').forEach(node => {
            const baseLabel = node.dataset.baseLabel || node.textContent.trim();
            node.dataset.baseLabel = baseLabel;

            if (state === 'sent') {
                node.textContent = `${baseLabel} | OK`;
            } else if (state === 'queued') {
                node.textContent = `${baseLabel} | ${this.t('prompts_file_status_queued', 'Queued')}`;
            } else if (state === 'failed') {
                node.textContent = `${baseLabel} | ${this.t('prompts_file_status_failed', 'Failed')}`;
            } else {
                node.textContent = baseLabel;
            }
        });
    },

    markPlaygroundFilesQueued: function(taskId) {
        this.setPlaygroundFilesVisualState('queued');
        this.updatePlaygroundFilesStatus(
            this.t('prompts_file_status_queued', 'Queued'),
            this.t('prompts_task_number', 'Task #{id}', {id: taskId})
        );
    },

    markPlaygroundFilesSent: function(modeLabel) {
        const sentAt = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        this.setPlaygroundFilesVisualState('sent');
        this.updatePlaygroundFilesStatus(
            this.t('prompts_file_status_sent', 'Sent'),
            this.t('prompts_file_sent_with_mode', '{mode} at {time}', {mode: modeLabel, time: sentAt})
        );
    },

    markPlaygroundFilesFailed: function() {
        this.setPlaygroundFilesVisualState('failed');
        this.updatePlaygroundFilesStatus(
            this.t('prompts_file_status_failed', 'Failed'),
            this.t('prompts_try_again', 'Try again')
        );
    },

    preparePlayground: function() {
        // Parse Jinja variables from content to generate input fields
        const content = this.editors.content.getValue();
        // Regex simple to find {{ variable }}. Not perfect but works for standard cases.
        const regex = /{{\s*([a-zA-Z0-9_]+)\s*}}/g;
        let match;
        const variables = new Set();

        while ((match = regex.exec(content)) !== null) {
            variables.add(match[1]);
        }

        const container = document.getElementById('playground-inputs-container');
        container.innerHTML = '';

        if (variables.size === 0) {
            container.innerHTML = `<div class="alert alert-info small">${t_js('no_variables_found')}</div>`;
            return;
        }

        variables.forEach(v => {
            const div = document.createElement('div');
            div.className = 'mb-2';
            div.innerHTML = `
                <label class="form-label small fw-bold text-muted">${v}</label>
                <textarea class="form-control form-control-sm playground-input" data-var="${v}" rows="1"></textarea>
            `;
            container.appendChild(div);
        });
    },

    executePrompt: async function() {
        if (!this.currentPrompt) return;
        this.stopPlaygroundPolling();
        this.clearPlaygroundOutputCopy();
        this.clearPlaygroundStructuredOutput();

        const inputs = {};
        document.querySelectorAll('.playground-input').forEach(el => {
            inputs[el.dataset.var] = el.value;
        });

        const modelOverride = (document.getElementById('playground-model') || {}).value || '';
        const asyncEnabled = this.isCurrentPromptAgent();

        const outputDiv = document.getElementById('playground-output');
        outputDiv.innerHTML = '<div class="text-center mt-5"><div class="spinner-border text-primary"></div></div>';

        // Clear metrics
        document.getElementById('metric-latency').textContent = '-';
        document.getElementById('metric-tokens').textContent = '-';

        const startTime = performance.now();
        let keepRunStateWhilePolling = false;

        this.setPlaygroundRunState(true);
        try {
            const files = await this.collectPlaygroundFiles();
            if (files.length > 0) {
                this.setPlaygroundFilesVisualState('pending');
                this.updatePlaygroundFilesStatus('Sending...', asyncEnabled ? 'async execution' : 'sync execution');
            }
            if (asyncEnabled) {
                keepRunStateWhilePolling = true;
                await this.executePromptAsync(inputs, modelOverride, files, startTime);
            } else {
                await this.executePromptSync(inputs, modelOverride, files, startTime);
            }
        } catch (err) {
            this.clearPlaygroundOutputCopy();
            this.clearPlaygroundStructuredOutput();
            this.markPlaygroundFilesFailed();
            outputDiv.innerHTML = `<div class="text-danger">${this.t(
                'prompts_execution_error',
                'Execution Error: {message}',
                {message: err.message || this.t('unknown_server_error', 'Unknown error')}
            )}</div>`;
        } finally {
            if (!keepRunStateWhilePolling || !this.playgroundTaskId) {
                this.setPlaygroundRunState(false);
            }
        }
    },

    executePromptSync: async function(inputs, modelOverride, files, startTime) {
        const payload = {
            prompt_name: this.currentPrompt.name,
            client_data: inputs,
            ignore_history: true,
            files: files,
            ...(modelOverride ? { model: modelOverride } : {})
        };

        const response = await fetch(this.endpoints.execute, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok || data.error) {
            throw new Error(data.error_message || data.error || 'Execution failed');
        }

        const latencySeconds = this.formatPlaygroundLatencySeconds(startTime);
        document.getElementById('metric-latency').textContent = latencySeconds;
        document.getElementById('metric-tokens').textContent = (data.stats && data.stats.total_tokens) || '-';

        const content = data.answer || '(Empty response)';
        this.renderPlaygroundResult(content, data.structured_output);
        this.markPlaygroundFilesSent(this.t('prompts_sync_label', 'Sync'));
    },

    executePromptAsync: async function(inputs, modelOverride, files, startTime) {
        const taskPayload = {
            user_identifier: window.IAT_CONFIG.userIdentifier || 'admin',
            task_type: 'PROMPT_EXECUTION',
            prompt_name: this.currentPrompt.name,
            client_data: {
                ...inputs,
                ...(modelOverride ? { model: modelOverride } : {})
            },
            files: files
        };

        const response = await fetch(this.endpoints.tasks, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskPayload)
        });

        const data = await response.json();
        if (!response.ok || !data.task_id) {
            throw new Error(data.error || data.error_message || 'Task creation failed');
        }

        this.playgroundTaskId = data.task_id;
        this.renderPlaygroundAsyncWaiting(data.task_id, 0);
        this.markPlaygroundFilesSent(this.t('prompts_async_queued_label', 'Async queued #{id}', {id: data.task_id}));
        this.pollPlaygroundTask(data.task_id, startTime, 0);
    },

    pollPlaygroundTask: async function(taskId, startTime, attempt) {
        const maxAttempts = 200;
        const pollDelayMs = 2500;
        const outputDiv = document.getElementById('playground-output');

        try {
            const response = await fetch(`${this.endpoints.tasks}/${taskId}`, { method: 'GET' });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || `Could not load task ${taskId}`);
            }

            const status = (data.status || '').toLowerCase();
            if (['executed', 'failed', 'approved', 'rejected'].includes(status)) {
                this.stopPlaygroundPolling();
                this.setPlaygroundRunState(false);
                const latencySeconds = this.formatPlaygroundLatencySeconds(startTime);
                document.getElementById('metric-latency').textContent = latencySeconds;

                if (status === 'executed') {
                    const executionResult = data.execution_result || {};
                    const answer = executionResult.answer || '(Empty response)';
                    const tokens = (executionResult.stats && executionResult.stats.total_tokens) || '-';
                    document.getElementById('metric-tokens').textContent = tokens;
                    this.renderPlaygroundResult(answer, executionResult.structured_output);
                    this.markPlaygroundFilesSent(this.t('prompts_async_label', 'Async'));
                    return;
                }

                this.clearPlaygroundOutputCopy();
                this.clearPlaygroundStructuredOutput();
                document.getElementById('metric-tokens').textContent = '-';
                outputDiv.innerHTML = `<div class="text-danger p-3 border border-danger bg-danger-subtle rounded">${data.error_msg || `Task finished with status: ${status}`}</div>`;
                this.markPlaygroundFilesFailed();
                return;
            }
        } catch (err) {
            if (attempt >= maxAttempts) {
                this.stopPlaygroundPolling();
                this.setPlaygroundRunState(false);
                this.clearPlaygroundOutputCopy();
                this.clearPlaygroundStructuredOutput();
                this.markPlaygroundFilesFailed();
                outputDiv.innerHTML = `<div class="text-danger">${this.t(
                    'prompts_polling_error',
                    'Polling error: {message}',
                    {message: err.message || this.t('unknown_server_error', 'Unknown error')}
                )}</div>`;
                return;
            }
        }

        if (attempt >= maxAttempts) {
            this.stopPlaygroundPolling();
            this.setPlaygroundRunState(false);
            this.clearPlaygroundOutputCopy();
            this.clearPlaygroundStructuredOutput();
            this.markPlaygroundFilesFailed();
            outputDiv.innerHTML = `<div class="text-danger">${this.t('prompts_task_timeout', 'Task timeout while waiting for result.')}</div>`;
            return;
        }

        this.renderPlaygroundAsyncWaiting(taskId, attempt + 1);

        this.playgroundPollTimer = setTimeout(() => {
            this.pollPlaygroundTask(taskId, startTime, attempt + 1);
        }, pollDelayMs);
    },

    // --- DIRTY STATE MANAGEMENT ---

    markDirty: function() {
        if (!this.isEditable()) return;
        if (this.isDirty) return;
        this.isDirty = true;
        const btn = document.getElementById('btn-save-prompt');
        if (btn) {
            btn.innerHTML = `<i class="bi bi-save me-1"></i> ${this.t('prompts_save_btn', 'Save')} *`;
            btn.classList.remove('btn-outline-primary');
            btn.classList.add('btn-primary');
        }
    },

    resetDirty: function() {
        this.isDirty = false;
        const btn = document.getElementById('btn-save-prompt');
        if (btn) {
            btn.innerHTML = `<i class="bi bi-save me-1"></i> ${this.t('prompts_save_btn', 'Save')}`;
            btn.classList.add('btn-outline-primary');
            btn.classList.remove('btn-primary');
        }
    },

    showUnsavedAlert: function(onConfirm) {
        const modalEl = document.getElementById('admin-alert-modal');
        if (!modalEl) {
            // Fallback if modal not found
            if (confirm("You have unsaved changes. Are you sure you want to discard them?")) {
                onConfirm();
            }
            return;
        }

        // Configure Modal
        const btnConfirm = document.getElementById('admin-alert-confirm-btn');

        // Clone button to remove previous event listeners
        const newBtn = btnConfirm.cloneNode(true);
        btnConfirm.parentNode.replaceChild(newBtn, btnConfirm);

        newBtn.onclick = () => {
            const modal = bootstrap.Modal.getInstance(modalEl);
            modal.hide();
            onConfirm();
        };

        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    },

    // --- MODAL ACTIONS ---

    createNewPromptModal: function() {
        if (!this.isEditable()) {
            this.notifyReadOnly();
            return;
        }
        const modalEl = document.getElementById('modal-new-prompt');

        // Reset fields
        document.getElementById('new-prompt-name').value = '';
        document.getElementById('new-prompt-description').value = '';

        // Reset category to the placeholder ("Select category...")
        const catSelect = document.getElementById('new-prompt-category');
        if (catSelect) catSelect.value = '';

        // Explicitly set the SELECT element's value to 'company'
        const typeSelect = document.getElementById('new-prompt-type');
        if (typeSelect) {
            typeSelect.value = 'company';
        }

        this.onPromptTypeChange(); // Ensure correct visibility state

        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    },

    onPromptTypeChange: function() {
        const typeSelect = document.getElementById('new-prompt-type');
        const catContainer = document.getElementById('container-new-prompt-category');
        const catSelect = document.getElementById('new-prompt-category');

        if (!typeSelect || !catContainer) return;

        const val = typeSelect.value;

        // Company and agent prompts always require category
        const requiresCategory = (val === 'company' || val === 'agent');
        catContainer.style.display = requiresCategory ? 'block' : 'none';

        if (catSelect) {
            catSelect.disabled = false;
            if (!requiresCategory) {
                catSelect.value = '';
            }
        }
    },

    createPrompt: function() {
        if (!this.isEditable()) {
            this.notifyReadOnly();
            return;
        }
        const nameInput = document.getElementById('new-prompt-name');
        const descInput = document.getElementById('new-prompt-description');
        const typeInput = document.getElementById('new-prompt-type');
        const catInput = document.getElementById('new-prompt-category');

        const name = nameInput.value.trim().toLowerCase();
        const description = descInput ? descInput.value.trim() : "";
        const type = typeInput.value;
        let category = catInput.value.trim();

        if (!name) {
            if (window.toastr) toastr.warning(this.t('prompts_name_required', 'Name is required'));
            return;
        }

        if (!this.supportedPromptTypes.includes(type)) {
            if (window.toastr) toastr.error(this.t('prompts_invalid_type', 'Invalid prompt type'));
            return;
        }

        if (!category) {
            if (window.toastr) toastr.warning(this.t('prompts_category_required', 'Category is required for this prompt type'));
            return;
        }

        // Backend Endpoint: POST /api/prompts
        const payload = {
            name: name,
            category: category,
            content: "", // Start empty
            description: description,
            prompt_type: type,
            active: true
        };

        const btn = document.querySelector('#modal-new-prompt .btn-primary-custom');
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = this.t('prompts_creating', 'Creating...');

        fetch(this.endpoints.list, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'error') throw new Error(data.message);

                if (window.toastr) {
                    toastr.success(this.t('prompts_created_ok', 'Prompt "{name}" created', {name}));
                }

                // Hide modal
                const modalEl = document.getElementById('modal-new-prompt');
                const modal = bootstrap.Modal.getInstance(modalEl);
                modal.hide();

                // Reload list
                this.loadPromptsList();
            })
            .catch(err => {
                console.error("Create error:", err);
                if (window.toastr) toastr.error(err.message || this.t('prompts_create_failed', 'Failed to create prompt'));
            })
            .finally(() => {
                btn.disabled = false;
                btn.textContent = originalText;
            });
    },

    // 1. Triggered by the Trash Icon
    deletePrompt: function() {
        if (!this.isEditable()) {
            this.notifyReadOnly();
            return;
        }
        if (!this.currentPrompt) return;

        // Show the Bootstrap Modal
        const modalEl = document.getElementById('prompt-delete-modal');
        if (modalEl) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
        }
    },

    // 2. Triggered by the Modal's Delete Button
    executeDelete: function() {
        if (!this.isEditable()) {
            this.notifyReadOnly();
            return;
        }
        if (!this.currentPrompt) return;
        const name = this.currentPrompt.name;

        const url = `${this.endpoints.list}/${name}`;
        const btn = document.getElementById('btn-prompt-confirm-delete');

        if(btn) btn.disabled = true;

        fetch(url, {
            method: 'DELETE'
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'error') throw new Error(data.message);

                if (window.toastr) toastr.success(this.t('prompts_deleted_ok', 'Prompt deleted'));

                // Hide modal
                const modalEl = document.getElementById('prompt-delete-modal');
                const modal = bootstrap.Modal.getInstance(modalEl);
                if(modal) modal.hide();

                // Clear workspace
                this.currentPrompt = null;
                document.getElementById('workspace-container').style.setProperty('display', 'none', 'important');
                document.getElementById('workspace-placeholder').classList.remove('d-none');
                document.getElementById('prompt-actions-toolbar').style.visibility = 'hidden';

                // Reset Header Info
                document.getElementById('current-prompt-name').textContent = 'No Prompt Selected';
                document.getElementById('current-prompt-category').textContent = '';
                const typeBadge = document.getElementById('current-prompt-type-badge');
                if (typeBadge) typeBadge.style.visibility = 'hidden';

                // Reload list
                this.loadPromptsList();
            })
            .catch(err => {
                console.error("Delete error:", err);
                if (window.toastr) toastr.error(err.message || this.t('prompts_delete_failed', 'Failed to delete prompt'));
            })
            .finally(() => {
                if(btn) btn.disabled = false;
            });
    },

    populateSelectors: function() {
        // 1. Populate Filter Type (Left Panel)
        const filterSelect = document.getElementById('prompt-filter-type');
        if (filterSelect) {
            // Preserve current selection if reloading
            const currentVal = filterSelect.value;

            // Clear but keep "All"
            filterSelect.innerHTML = '<option value="all">All</option>';

            // Add supported prompt types dynamically
            const types = this.optionsCache.types.length > 0
                ? this.optionsCache.types
                : this.supportedPromptTypes;

            types.forEach(t => {
                const display = t.charAt(0).toUpperCase() + t.slice(1);
                // Use standard DOM creation
                const opt = document.createElement('option');
                opt.value = t;
                opt.text = display.substring(0, 4); // Shorten for the small select (e.g. Comp, Syst)
                filterSelect.appendChild(opt);
            });

            // Restore value when valid or default to company
            if (currentVal && (currentVal === 'all' || types.includes(currentVal))) {
                filterSelect.value = currentVal;
            } else {
                filterSelect.value = 'company'; // Default requested by user
            }
        }

        // 2. Populate Modal Type (Create Modal)
        const modalTypeSelect = document.getElementById('new-prompt-type');
        if (modalTypeSelect) {
            const types = this.optionsCache.types.length > 0
                ? this.optionsCache.types
                : this.supportedPromptTypes;
            modalTypeSelect.innerHTML = '';
            types.forEach(t => {
                const display = t.charAt(0).toUpperCase() + t.slice(1);
                const opt = document.createElement('option');
                opt.value = t;
                opt.text = display;
                if (t === 'company') opt.selected = true;
                modalTypeSelect.appendChild(opt);
            });
        }

        // 3. Populate Category Selectors (Create Modal & Config Drawer)
        const populateCat = (selectId) => {
            const el = document.getElementById(selectId);
            if (!el) return;

            // FIX: Save current value before clearing to attempt restore
            const previousValue = el.value;

            el.innerHTML = '';

            // Placeholder Option (Critical for Modal default state)
            const placeholder = document.createElement('option');
            placeholder.value = "";
            placeholder.text = "Select category...";
            placeholder.disabled = true;
            placeholder.selected = true; // Force selection initially
            el.appendChild(placeholder);

            this.optionsCache.categories.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c;
                opt.text = c;
                el.appendChild(opt);
            });

            // If this is the config selector AND we have a current prompt, force its category.
            // This handles the Race Condition where metadata loads AFTER the prompt is selected.
            if (selectId === 'config-category' && this.currentPrompt && this.currentPrompt.category) {
                const target = this.currentPrompt.category.toLowerCase();
                Array.from(el.options).forEach(opt => {
                    if (opt.value.toLowerCase() === target) el.value = opt.value;
                });
            }
            // Otherwise, try to keep the user's manual selection if it's still valid
            else if (previousValue) {
                el.value = previousValue;
            }
        };

        populateCat('new-prompt-category');
        populateCat('config-category');

        // 4. Populate Playground Model Selector (NEW)
        const modelSelect = document.getElementById('playground-model');
        if (modelSelect) {
            const currentVal = modelSelect.value;
            // Default / Placeholder
            modelSelect.innerHTML = '<option value="" selected>Default (System)</option>';

            this.optionsCache.models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.text = m;
                modelSelect.appendChild(opt);
            });

            // Restore selection if needed
            if (currentVal) modelSelect.value = currentVal;
        }
    },

    // --- CATEGORY MANAGER (NEW) ---

    openCategoryManager: function() {
        if (!this.isEditable()) {
            this.notifyReadOnly();
            return;
        }
        if (typeof DashboardShell !== 'undefined') {
            DashboardShell.openCategoryMaintainer('prompt_categories', 'Manage Prompt Categories');
        } else {
            console.error("DashboardShell not found");
        }
    },

    renderCategoryList: function(categories) {
        const list = document.getElementById('cat-man-list');
        list.innerHTML = '';

        if (categories.length === 0) {
            list.innerHTML = '<div class="text-center p-3 text-muted small">No categories found.</div>';
            return;
        }

        // Sort by order
        categories.sort((a, b) => a.order - b.order);

        categories.forEach((cat, index) => {
            const item = document.createElement('div');
            item.className = 'list-group-item d-flex align-items-center justify-content-between p-2';

            // Layout: [DragHandle] [Order Input] [Name Input] [Delete Btn]
            item.innerHTML = `
                <div class="d-flex align-items-center gap-2 flex-grow-1">
                    <i class="bi bi-grip-vertical text-muted opacity-50" style="cursor: move;"></i>
                    <input type="number" class="form-control form-control-sm text-center p-1" style="width: 40px;" value="${cat.order}" readonly>
                    <input type="text" class="form-control form-control-sm border-0 bg-transparent fw-bold" value="${cat.name}" readonly>
                </div>
                <div>
                     <button class="btn btn-sm btn-link text-danger p-0 ms-2" title="Delete" onclick="if(confirm('Delete category?')) { alert('Implement Delete API'); }">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            `;
            list.appendChild(item);
        });
    },

    addCategory: function() {
        const input = document.getElementById('cat-man-new-name');
        const name = input.value.trim();
        if(!name) return;

        // TODO: Call API POST /categories
        alert(`Implement API: Create Category '${name}'`);
        input.value = '';
        // Then reload list
        // this.loadCategoriesForManager();
    }


};

// Register module
if (typeof DashboardShell !== 'undefined') {
    DashboardShell.registerModule('prompts_manager', PromptsManagerModule);
}
