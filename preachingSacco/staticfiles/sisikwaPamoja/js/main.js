/* ══════════════════════════════
   SISIPAMOJA WELFARE - MAIN JS
══════════════════════════════ */

document.addEventListener('DOMContentLoaded', function () {

    // ── 1. Scroll Reveal Animation
    const revealObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    revealObserver.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.12 }
    );

    document.querySelectorAll('.reveal')
        .forEach(el => revealObserver.observe(el));


    // ── 2. Navbar shadow on scroll
    const navbar = document.querySelector('.navbar');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 60) {
            navbar.classList.add('navbar-scroll');
        } else {
            navbar.classList.remove('navbar-scroll');
        }
    });


    // ── 3. Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]')
        .forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                const target = document.querySelector(
                    this.getAttribute('href')
                );
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });


    // ── 4. Counter animation for stats
    function animateCounter(el, target, duration = 2000) {
        let start = 0;
        const step = target / (duration / 16);
        const timer = setInterval(() => {
            start += step;
            if (start >= target) {
                el.textContent = target + '+';
                clearInterval(timer);
            } else {
                el.textContent = Math.floor(start) + '+';
            }
        }, 16);
    }

    const statsObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const el = entry.target;
                    const target = parseInt(
                        el.getAttribute('data-count')
                    );
                    animateCounter(el, target);
                    statsObserver.unobserve(el);
                }
            });
        },
        { threshold: 0.5 }
    );

    document.querySelectorAll('[data-count]')
        .forEach(el => statsObserver.observe(el));


    // ── 5. Logout modal trigger
    const logoutBtn = document.getElementById('logoutBtn');
    const logoutModal = document.getElementById('logoutModal');

    if (logoutBtn && logoutModal) {
        logoutBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            const modal = new bootstrap.Modal(logoutModal);
            modal.show();
        });
    }


    // ── 6. Active nav link on scroll
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link-item');

    window.addEventListener('scroll', () => {
        let current = '';
        sections.forEach(section => {
            const sectionTop = section.offsetTop - 100;
            if (window.scrollY >= sectionTop) {
                current = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.style.background = '';
            if (link.getAttribute('href') === '#' + current) {
                link.style.background = 'rgba(255,255,255,0.15)';
                link.style.color = '#fff';
            }
        });
    });

});