// Global variables
let clientsData = [];
let serversData = [];
let allData = [];
let filteredData = [];
let currentView = 'grid';
let currentPage = 1;
let itemsPerPage = 20;
let totalPages = 1;

// DOM Elements
const navItems = document.querySelectorAll('.nav-item');
const pages = document.querySelectorAll('.page');
const searchInput = document.getElementById('search-input');
const typeFilter = document.getElementById('type-filter');
const categoryFilter = document.getElementById('category-filter');
const languageFilter = document.getElementById('language-filter');
const searchResults = document.getElementById('search-results');
const resultsCount = document.getElementById('results-count');
const viewButtons = document.querySelectorAll('.view-btn');
const modal = document.getElementById('project-modal');
const modalTitle = document.getElementById('modal-title');
const modalBody = document.getElementById('modal-body');
const modalClose = document.querySelector('.modal-close');
const paginationContainer = document.getElementById('pagination-container');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const pageNumbers = document.getElementById('page-numbers');
const paginationInfo = document.getElementById('pagination-info');

// Initialize app
document.addEventListener('DOMContentLoaded', async () => {
    await loadData();
    setupEventListeners();
    updateDashboard();
    initializeSearch();
});

// Load data from JSON files with optimization
async function loadData() {
    try {
        showLoading();
        
        const [clientsResponse, serversResponse] = await Promise.all([
            fetch('mcpso_clients_cleaned.json'),
            fetch('mcpso_servers_cleaned.json')
        ]);

        if (!clientsResponse.ok || !serversResponse.ok) {
            throw new Error('Failed to fetch data');
        }

        clientsData = await clientsResponse.json();
        serversData = await serversResponse.json();
        
        // Combine all data and deduplicate by GitHub repository
        const rawData = [
            ...clientsData.map(item => ({ ...item, type: 'client' })),
            ...serversData.map(item => ({ ...item, type: 'server' }))
        ];
        
        // Process and deduplicate data
        allData = processAndDeduplicateData(rawData);
        filteredData = [...allData];
        
        console.log(`Loaded ${clientsData.length} clients and ${serversData.length} servers (${allData.length} total projects)`);
        
        hideLoading();
    } catch (error) {
        console.error('Error loading data:', error);
        showError('Failed to load data. Please refresh the page.');
        hideLoading();
    }
}

// Setup event listeners
function setupEventListeners() {
    // Navigation
    navItems.forEach(item => {
        item.addEventListener('click', () => switchPage(item.dataset.page));
    });

    // Search and filters
    searchInput.addEventListener('input', debounce(performSearch, 300));
    typeFilter.addEventListener('change', performSearch);
    categoryFilter.addEventListener('change', performSearch);
    languageFilter.addEventListener('change', performSearch);

    // View toggle
    viewButtons.forEach(btn => {
        btn.addEventListener('click', () => toggleView(btn.dataset.view));
    });

    // Modal
    modalClose.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });

    // Pagination
    prevBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            renderSearchResults();
            renderPagination();
        }
    });

    nextBtn.addEventListener('click', () => {
        if (currentPage < totalPages) {
            currentPage++;
            renderSearchResults();
            renderPagination();
        }
    });
}

// Switch between pages
function switchPage(pageId) {
    // Update navigation
    navItems.forEach(item => {
        item.classList.toggle('active', item.dataset.page === pageId);
    });

    // Update pages
    pages.forEach(page => {
        page.classList.toggle('active', page.id === pageId);
    });

    // Initialize page-specific content
    if (pageId === 'search') {
        // Reset pagination when switching to search page
        currentPage = 1;
        performSearch();
        populateFilters();
    }
}

// Process and deduplicate data based on GitHub repository
function processAndDeduplicateData(rawData) {
    const githubMap = new Map();
    const processedData = [];
    
    for (const item of rawData) {
        // Only process items with valid GitHub data
        if (item.github && item.github.full_name && item.github.stargazers_count >= 0) {
            const githubKey = item.github.full_name.toLowerCase();
            
            // Extract real project name from GitHub URL
            const realName = extractProjectNameFromGithub(item.github.full_name);
            
            // Check if we already have this repository
            if (githubMap.has(githubKey)) {
                const existing = githubMap.get(githubKey);
                // Keep the one with more complete information or higher stars
                if (item.github.stargazers_count > existing.github.stargazers_count ||
                    (item.github.stargazers_count === existing.github.stargazers_count && 
                     item.description && item.description.length > (existing.description || '').length)) {
                    githubMap.set(githubKey, { ...item, displayName: realName });
                }
            } else {
                githubMap.set(githubKey, { ...item, displayName: realName });
            }
        } else {
            // For items without GitHub data, keep them as is but filter out obviously invalid names
            if (isValidProjectName(item.name)) {
                processedData.push({ ...item, displayName: item.name });
            }
        }
    }
    
    // Add deduplicated GitHub projects
    processedData.push(...Array.from(githubMap.values()));
    
    return processedData;
}

// Extract project name from GitHub full_name
function extractProjectNameFromGithub(fullName) {
    if (!fullName) return 'Unknown';
    const parts = fullName.split('/');
    return parts[parts.length - 1] || 'Unknown';
}

// Check if project name is valid (filter out test names)
function isValidProjectName(name) {
    if (!name || typeof name !== 'string') return false;
    
    const invalidPatterns = [
        /^[0-9]+$/,        // Pure numbers: 1, 11, 12, 11111
        /^test$/i,         // Just "test"
        /^[a-z]$/i,        // Single letters
        /^.{1,2}$/,        // Too short (1-2 characters)
    ];
    
    return !invalidPatterns.some(pattern => pattern.test(name.trim()));
}

// Update dashboard statistics and charts
function updateDashboard() {
    updateStatistics();
    renderCharts();
    renderTopProjects();
}

// Update statistics
function updateStatistics() {
    const clientsCount = clientsData.length;
    const serversCount = serversData.length;
    
    const categories = new Set([
        ...clientsData.map(item => item.category).filter(Boolean),
        ...serversData.map(item => item.category).filter(Boolean)
    ]);
    
    const totalStars = allData
        .filter(item => item.github && item.github.stargazers_count)
        .reduce((sum, item) => sum + item.github.stargazers_count, 0);

    animateNumber('clients-count', clientsCount);
    animateNumber('servers-count', serversCount);
    animateNumber('categories-count', categories.size);
    animateNumber('stars-count', formatNumber(totalStars));
}

// Animate numbers
function animateNumber(elementId, target) {
    const element = document.getElementById(elementId);
    const start = 0;
    const duration = 1000;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const current = Math.floor(progress * (
            typeof target === 'string' 
                ? parseInt(target.replace(/[^\d]/g, '')) 
                : target
        ));
        
        element.textContent = typeof target === 'string' 
            ? formatNumber(current) 
            : current;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.textContent = target;
        }
    }
    
    requestAnimationFrame(update);
}

// Format numbers
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// Render charts
function renderCharts() {
    renderCategoryChart();
    renderLanguageChart();
}

// Category distribution chart
function renderCategoryChart() {
    const ctx = document.getElementById('categoryChart').getContext('2d');
    
    const categoryCount = {};
    allData.forEach(item => {
        if (item.category) {
            const category = formatCategoryName(item.category);
            categoryCount[category] = (categoryCount[category] || 0) + 1;
        }
    });

    const sortedCategories = Object.entries(categoryCount)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8);

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: sortedCategories.map(([category]) => category),
            datasets: [{
                data: sortedCategories.map(([, count]) => count),
                backgroundColor: [
                    '#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', 
                    '#ef4444', '#06b6d4', '#84cc16', '#f97316'
                ],
                borderWidth: 0,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        font: { family: 'Inter' }
                    }
                }
            }
        }
    });
}

// Language distribution chart
function renderLanguageChart() {
    const ctx = document.getElementById('languageChart').getContext('2d');
    
    const languageCount = {};
    allData.forEach(item => {
        if (item.github && item.github.language) {
            const lang = item.github.language;
            languageCount[lang] = (languageCount[lang] || 0) + 1;
        }
    });

    const sortedLanguages = Object.entries(languageCount)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sortedLanguages.map(([lang]) => lang),
            datasets: [{
                label: 'Projects',
                data: sortedLanguages.map(([, count]) => count),
                backgroundColor: '#3b82f6',
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#f3f4f6' },
                    ticks: { font: { family: 'Inter' } }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { family: 'Inter' } }
                }
            }
        }
    });
}

// Render top projects
function renderTopProjects() {
    const container = document.getElementById('top-projects');
    
    const topProjects = allData
        .filter(item => item.github && item.github.stargazers_count > 0)
        .sort((a, b) => b.github.stargazers_count - a.github.stargazers_count)
        .slice(0, 10);

    if (topProjects.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-star"></i>
                <p>No projects with GitHub data found</p>
            </div>
        `;
        return;
    }

    container.innerHTML = topProjects.map((project, index) => `
        <div class="project-item" onclick="showProjectModal('${project.id}')">
            <div class="project-rank">#${index + 1}</div>
            <div class="project-github">
                <a href="${project.url}" target="_blank" onclick="event.stopPropagation()">
                    <i class="fab fa-github"></i>
                    ${project.github.full_name}
                </a>
            </div>
            <div class="project-stars">
                <i class="fas fa-star"></i>
                ${formatNumber(project.github.stargazers_count)}
            </div>
        </div>
    `).join('');
}

// Initialize search page
function initializeSearch() {
    populateFilters();
    performSearch();
}

// Populate filter dropdowns
function populateFilters() {
    // Categories
    const categories = [...new Set(allData.map(item => item.category).filter(Boolean))].sort();
    populateSelect(categoryFilter, categories, formatCategoryName);

    // Languages
    const languages = [...new Set(allData
        .filter(item => item.github && item.github.language)
        .map(item => item.github.language)
    )].sort();
    populateSelect(languageFilter, languages);
}

// Populate select element
function populateSelect(selectElement, options, formatter = null) {
    // Clear existing options (except first one)
    while (selectElement.children.length > 1) {
        selectElement.removeChild(selectElement.lastChild);
    }

    options.forEach(option => {
        const optionEl = document.createElement('option');
        optionEl.value = option;
        optionEl.textContent = formatter ? formatter(option) : option;
        selectElement.appendChild(optionEl);
    });
}

// Perform search and filtering
function performSearch() {
    const query = searchInput.value.toLowerCase().trim();
    const type = typeFilter.value;
    const category = categoryFilter.value;
    const language = languageFilter.value;

    filteredData = allData.filter(item => {
        // Text search (use displayName for better search experience)
        const searchName = item.displayName || item.name;
        const matchesQuery = !query || 
            searchName.toLowerCase().includes(query) ||
            (item.description || '').toLowerCase().includes(query) ||
            item.author_name.toLowerCase().includes(query) ||
            (item.tags || '').toLowerCase().includes(query);

        // Type filter
        const matchesType = !type || item.type === type;

        // Category filter
        const matchesCategory = !category || item.category === category;

        // Language filter
        const matchesLanguage = !language || 
            (item.github && item.github.language === language);

        return matchesQuery && matchesType && matchesCategory && matchesLanguage;
    });

    // Reset to first page when search changes
    currentPage = 1;
    totalPages = Math.ceil(filteredData.length / itemsPerPage);
    
    updateResultsCount();
    renderSearchResults();
    renderPagination();
}

// Update results count
function updateResultsCount() {
    const count = filteredData.length;
    resultsCount.textContent = `${count} result${count !== 1 ? 's' : ''}`;
}

// Render search results
function renderSearchResults() {
    const container = searchResults;
    
    if (filteredData.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-search"></i>
                <h3>No results found</h3>
                <p>Try adjusting your search criteria</p>
            </div>
        `;
        paginationContainer.style.display = 'none';
        return;
    }

    // Calculate pagination
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const currentItems = filteredData.slice(startIndex, endIndex);

    container.className = `results-grid ${currentView === 'list' ? 'list-view' : ''}`;
    
    container.innerHTML = currentItems.map(item => createProjectCard(item)).join('');
    paginationContainer.style.display = 'block';
}

// Create project card HTML
function createProjectCard(item) {
    const tags = item.tags ? item.tags.split(',').map(tag => tag.trim()).slice(0, 4) : [];
    const github = item.github;

    return `
        <div class="project-card" onclick="showProjectModal('${item.id}')">
            <div class="project-header">
                <div class="project-info">
                    <div class="project-title">${escapeHtml(item.displayName || item.name)}</div>
                    <div class="project-author">by ${escapeHtml(item.author_name)}</div>
                </div>
                <span class="project-type ${item.type}">${item.type}</span>
            </div>
            
            <div class="project-meta">
                ${github ? `
                    <div class="project-stats">
                        <span class="stat-item">
                            <i class="fas fa-star"></i>
                            ${formatNumber(github.stargazers_count || 0)}
                        </span>
                        <span class="stat-item">
                            <i class="fas fa-code-branch"></i>
                            ${formatNumber(github.forks_count || 0)}
                        </span>
                        ${github.language ? `
                            <span class="stat-item">
                                <i class="fas fa-code"></i>
                                ${escapeHtml(github.language)}
                            </span>
                        ` : ''}
                    </div>
                ` : ''}
                
                ${item.category ? `
                    <div class="category-badge">${formatCategoryName(item.category)}</div>
                ` : ''}
            </div>
            
            ${tags.length > 0 ? `
                <div class="project-tags">
                    ${tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                    ${tags.length > 4 ? `<span class="tag more">+${item.tags.split(',').length - 4}</span>` : ''}
                </div>
            ` : ''}
        </div>
    `;
}

// Toggle view mode
function toggleView(view) {
    currentView = view;
    viewButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
    renderSearchResults();
}

// Render pagination
function renderPagination() {
    if (totalPages <= 1) {
        paginationContainer.style.display = 'none';
        return;
    }

    paginationContainer.style.display = 'block';

    // Update prev/next buttons
    prevBtn.disabled = currentPage === 1;
    nextBtn.disabled = currentPage === totalPages;

    // Generate page numbers
    const maxVisiblePages = 7;
    let startPage, endPage;

    if (totalPages <= maxVisiblePages) {
        startPage = 1;
        endPage = totalPages;
    } else {
        const halfVisible = Math.floor(maxVisiblePages / 2);
        if (currentPage <= halfVisible) {
            startPage = 1;
            endPage = maxVisiblePages;
        } else if (currentPage + halfVisible >= totalPages) {
            startPage = totalPages - maxVisiblePages + 1;
            endPage = totalPages;
        } else {
            startPage = currentPage - halfVisible;
            endPage = currentPage + halfVisible;
        }
    }

    let pagesHTML = '';

    // First page and ellipsis
    if (startPage > 1) {
        pagesHTML += `<button class="page-number" onclick="goToPage(1)">1</button>`;
        if (startPage > 2) {
            pagesHTML += `<span class="page-number ellipsis">...</span>`;
        }
    }

    // Page numbers
    for (let i = startPage; i <= endPage; i++) {
        pagesHTML += `<button class="page-number ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
    }

    // Last page and ellipsis
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            pagesHTML += `<span class="page-number ellipsis">...</span>`;
        }
        pagesHTML += `<button class="page-number" onclick="goToPage(${totalPages})">${totalPages}</button>`;
    }

    pageNumbers.innerHTML = pagesHTML;

    // Update pagination info
    const startItem = (currentPage - 1) * itemsPerPage + 1;
    const endItem = Math.min(currentPage * itemsPerPage, filteredData.length);
    paginationInfo.textContent = `Showing ${startItem}-${endItem} of ${filteredData.length}`;
}

// Go to specific page
function goToPage(page) {
    if (page >= 1 && page <= totalPages && page !== currentPage) {
        currentPage = page;
        renderSearchResults();
        renderPagination();
        
        // Scroll to top of results
        searchResults.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// Show project modal
function showProjectModal(itemId) {
    const item = allData.find(project => project.id == itemId);
    if (!item) return;

    modalTitle.textContent = item.displayName || item.name;
    
    const github = item.github;
    const tags = item.tags ? item.tags.split(',').map(tag => tag.trim()) : [];
    
    modalBody.innerHTML = `
        <div class="modal-grid">
            <div class="modal-info">
                <div class="info-row">
                    <span class="info-label">Author</span>
                    <span class="info-value">${escapeHtml(item.author_name)}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Type</span>
                    <span class="info-value">
                        <span class="project-type ${item.type}">${item.type}</span>
                    </span>
                </div>
                ${item.category ? `
                    <div class="info-row">
                        <span class="info-label">Category</span>
                        <span class="info-value">
                            <span class="category-badge">${formatCategoryName(item.category)}</span>
                        </span>
                    </div>
                ` : ''}
                ${item.url ? `
                    <div class="info-row">
                        <span class="info-label">Website</span>
                        <span class="info-value">
                            <a href="${escapeHtml(item.url)}" target="_blank" class="external-link">
                                <i class="fas fa-external-link-alt"></i>
                                Visit Project
                            </a>
                        </span>
                    </div>
                ` : ''}
            </div>

            ${github ? `
                <div class="modal-github">
                    <h4><i class="fab fa-github"></i> GitHub Repository</h4>
                    <div class="github-stats">
                        <div class="github-stat">
                            <div class="github-stat-value">${formatNumber(github.stargazers_count || 0)}</div>
                            <div class="github-stat-label"><i class="fas fa-star"></i> Stars</div>
                        </div>
                        <div class="github-stat">
                            <div class="github-stat-value">${formatNumber(github.forks_count || 0)}</div>
                            <div class="github-stat-label"><i class="fas fa-code-branch"></i> Forks</div>
                        </div>
                        <div class="github-stat">
                            <div class="github-stat-value">${formatNumber(github.open_issues_count || 0)}</div>
                            <div class="github-stat-label"><i class="fas fa-exclamation-circle"></i> Issues</div>
                        </div>
                        <div class="github-stat">
                            <div class="github-stat-value">${formatNumber(github.contributors_count || 0)}</div>
                            <div class="github-stat-label"><i class="fas fa-users"></i> Contributors</div>
                        </div>
                        ${github.language ? `
                            <div class="github-stat">
                                <div class="github-stat-value">${escapeHtml(github.language)}</div>
                                <div class="github-stat-label"><i class="fas fa-code"></i> Language</div>
                            </div>
                        ` : ''}
                        ${github.license ? `
                            <div class="github-stat">
                                <div class="github-stat-value">${escapeHtml(github.license)}</div>
                                <div class="github-stat-label"><i class="fas fa-balance-scale"></i> License</div>
                            </div>
                        ` : ''}
                    </div>
                    ${github.full_name ? `
                        <a href="https://github.com/${escapeHtml(github.full_name)}" target="_blank" class="github-link">
                            <i class="fab fa-github"></i>
                            View on GitHub
                        </a>
                    ` : ''}
                </div>
            ` : ''}
        </div>
        
        ${item.description ? `
            <div class="modal-section">
                <h4>Description</h4>
                <p class="description-text">${escapeHtml(item.description)}</p>
            </div>
        ` : ''}
        
        ${tags.length > 0 ? `
            <div class="modal-section">
                <h4>Tags</h4>
                <div class="project-tags">
                    ${tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                </div>
            </div>
        ` : ''}
    `;
    
    modal.classList.add('active');
}

// Close modal
function closeModal() {
    modal.classList.remove('active');
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatCategoryName(category) {
    if (!category) return '';
    
    const categoryMap = {
        'developer-tools': 'Developer Tools',
        'communication': 'Communication',
        'ai-chatbot': 'AI Chatbot',
        'research-and-data': 'Research & Data',
        'security': 'Security',
        'speech-processing': 'Speech Processing',
        'location-services': 'Location Services',
        'browser-automation': 'Browser Automation',
        'databases': 'Databases',
        'knowledge-and-memory': 'Knowledge & Memory',
        'cloud-platforms': 'Cloud Platforms',
        'finance': 'Finance'
    };
    
    return categoryMap[category] || 
           category.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function showLoading() {
    // You can implement loading states here
    console.log('Loading...');
}

function hideLoading() {
    // You can implement hiding loading states here
    console.log('Loading complete');
}

function showError(message) {
    console.error(message);
    // You can implement error notification here
} 