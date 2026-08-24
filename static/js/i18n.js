const translations = {
    en: {
        page_title: "YourStats",
        nav_dashboard: "Dashboard",
        nav_history: "History",
        nav_analytics: "Analytics",
        btn_new_trade: "New Trade",
        page_heading: "Trading Analytics",
        page_subtitle: "Deep statistical analysis and distribution of your results.",
        long_positions: "LONG Positions",
        short_positions: "SHORT Positions",
        total_label: "Total",
        total_pnl: "Total PnL",
        win_rate: "Win Rate",
        psychology_title: "Psychological & Emotional Analysis",
        th_emotion: "Emotion / State",
        th_trades_count: "Trade Count",
        th_total_pnl: "Total PnL",
        no_data: "No data available yet."
    },
    ka: {
        page_title: "YourStats",
        nav_dashboard: "მთავარი",
        nav_history: "ისტორია",
        nav_analytics: "ანალიტიკა",
        btn_new_trade: "ახალი ტრეიდი",
        page_heading: "სავაჭრო ანალიტიკა",
        page_subtitle: "თქვენი შედეგების ღრმა სტატისტიკური ანალიზი და განაწილება.",
        long_positions: "LONG პოზიციები",
        short_positions: "SHORT პოზიციები",
        total_label: "სულ",
        total_pnl: "მთლიანი PnL",
        win_rate: "Win Rate",
        psychology_title: "ფსიქოლოგიური და ემოციური ანალიზი",
        th_emotion: "ემოცია / მდგომარეობა",
        th_trades_count: "ტრეიდების რაოდენობა",
        th_total_pnl: "ჯამური PnL",
        no_data: "მონაცემები ჯერ არ არის."
    },
    ru: {
        page_title: "YourStats",
        nav_dashboard: "Главная",
        nav_history: "История",
        nav_analytics: "Аналитика",
        btn_new_trade: "Новая сделка",
        page_heading: "Торговая аналитика",
        page_subtitle: "Глубокий статистический анализ и распределение ваших результатов.",
        long_positions: "LONG позиции",
        short_positions: "SHORT позиции",
        total_label: "Всего",
        total_pnl: "Общий PnL",
        win_rate: "Win Rate",
        psychology_title: "Психологический и эмоциональный анализ",
        th_emotion: "Эмоция / Состояние",
        th_trades_count: "Количество сделок",
        th_total_pnl: "Общий PnL",
        no_data: "Данные пока отсутствуют."
    },
    es: {
        page_title: "YourStats",
        nav_dashboard: "Inicio",
        nav_history: "Historial",
        nav_analytics: "Analítica",
        btn_new_trade: "Nueva operación",
        page_heading: "Analítica de Trading",
        page_subtitle: "Análisis estadístico profundo y distribución de tus resultados.",
        long_positions: "Posiciones LONG",
        short_positions: "Posiciones SHORT",
        total_label: "Total",
        total_pnl: "PnL Total",
        win_rate: "Win Rate",
        psychology_title: "Análisis Psicológico y Emocional",
        th_emotion: "Emoción / Estado",
        th_trades_count: "Nº de operaciones",
        th_total_pnl: "PnL Total",
        no_data: "No hay datos disponibles todavía."
    }
};

const langLabels = {
    'en': 'English',
    'ka': 'ქართული',
    'ru': 'Русский',
    'es': 'Español'
};

function applyTranslations(lang) {
    const t = translations[lang];
    if (!t) return;

    // 1. გადათარგმნე ყველა HTML ელემენტი, რომელსაც აქვს data-i18n ატრიბუტი
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key]) {
            el.innerText = t[key];
        }
    });

    // 2. განაახლე ნავბარში არჩეული ენის ტექსტი (მაგ: English, ქართული)
    const labelEl = document.getElementById('currentLangLabel');
    if (labelEl && langLabels[lang]) {
        labelEl.innerText = langLabels[lang];
    }
}

function changeLanguage(lang) {
    // ინახავს არჩეულ ენას ბრაუზერის მეხსიერებაში
    localStorage.setItem('selected_language', lang);
    applyTranslations(lang);
    
    const dropdown = document.getElementById('langDropdown');
    if (dropdown) dropdown.classList.add('hidden');
}

function toggleLangMenu() {
    const dropdown = document.getElementById('langDropdown');
    if (dropdown) dropdown.classList.toggle('hidden');
}

// გვერდის ჩატვირთვისთანავე ბრაუზერი ამოწმებს შენახულ ენას
document.addEventListener('DOMContentLoaded', () => {
    const savedLang = localStorage.getItem('selected_language') || 'en';
    applyTranslations(savedLang);
});

// მენიუს დახურვა ეკრანის სხვა ადგილას დაჭერისას
window.addEventListener('click', (e) => {
    const button = document.getElementById('langMenuButton');
    const dropdown = document.getElementById('langDropdown');
    if (button && dropdown && !button.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.add('hidden');
    }
});
