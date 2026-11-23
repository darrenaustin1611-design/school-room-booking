// EduReserve — Main JavaScript
// Clean, robust animation system using IntersectionObserver
// Particle canvas, scroll HUD, and modal handlers intact

document.addEventListener('DOMContentLoaded', () => {
    initModals();
    initAmbientSpotlight();
    initAmbientParticleCanvas();
    initScrollPhysics();
    initRevealAnimations();  // Replaces broken scroll-scrub
    initCounterRollups();
    initHorizontalSlideIns();
});

/* ==========================================================================
   1. Scroll Physics — Progress Bar, HUD Telemetry, Navbar Shrink
   ========================================================================== */
let globalScrollVelocity = 0;

function initScrollPhysics() {
    const progressBar = document.getElementById('scroll-progress-bar');
    const hudVelocity  = document.getElementById('hud-velocity');
    const hudProgress  = document.getElementById('hud-progress');
    const hudElement   = document.getElementById('scroll-telemetry');
    const navWrapper   = document.getElementById('navbar-wrapper');

    let lastScrollY = window.scrollY;
    let lastTime    = performance.now();
    let smoothVelocity = 0;

    function onScrollFrame(currentTime) {
        const currentScrollY = window.scrollY;
        const maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
        const scrollPercent = Math.min(100, Math.max(0, (currentScrollY / maxScroll) * 100));

        // Progress bar
        if (progressBar) {
            progressBar.style.transform = `scaleX(${scrollPercent / 100})`;
        }

        // Velocity
        const dt = Math.max(10, currentTime - lastTime);
        const scrollDelta = currentScrollY - lastScrollY;
        const rawVelocity = Math.abs(scrollDelta) / (dt / 1000);
        smoothVelocity = smoothVelocity * 0.82 + rawVelocity * 0.18;
        globalScrollVelocity = scrollDelta * 0.35;

        // HUD
        if (hudVelocity) hudVelocity.innerText = Math.round(smoothVelocity).toString().padStart(2, '0');
        if (hudProgress) hudProgress.innerText = `${Math.round(scrollPercent)}%`;

        if (hudElement) {
            if (smoothVelocity > 25) {
                hudElement.style.borderColor = 'var(--border-glow)';
                hudElement.style.boxShadow = '0 20px 45px -8px rgba(0,0,0,.65), 0 0 25px rgba(159,227,206,.3)';
            } else {
                hudElement.style.borderColor = 'var(--border-card)';
                hudElement.style.boxShadow = '0 16px 36px -8px rgba(0,0,0,.55)';
            }
        }

        // Navbar shrink
        if (navWrapper) {
            navWrapper.classList.toggle('scrolled', currentScrollY > 40);
        }

        lastScrollY = currentScrollY;
        lastTime = currentTime;
        requestAnimationFrame(onScrollFrame);
    }

    requestAnimationFrame(onScrollFrame);
}

/* ==========================================================================
   2. Reveal Animations — IntersectionObserver based (fire-once, stays visible)
   This replaces the broken continuous rAF loop that kept elements at opacity:0
   ========================================================================== */
function initRevealAnimations() {
    // Add reveal-pending class to all cards & hero elements
    const revealTargets = document.querySelectorAll(
        '.card, .spacious-hero, .prompt-banner, .grid-cards > *, [data-reveal]'
    );

    revealTargets.forEach((el, index) => {
        el.classList.add('reveal-pending');
        // Stagger by index within parent
        const siblingIndex = Array.from(el.parentElement?.children || []).indexOf(el);
        el.style.transitionDelay = `${Math.min(siblingIndex * 0.07, 0.35)}s`;
    });

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('reveal-visible');
                entry.target.classList.remove('reveal-pending');
                // Fire once — unobserve after reveal
                observer.unobserve(entry.target);
                // Clear delay after animation completes so hover effects work
                setTimeout(() => {
                    entry.target.style.transitionDelay = '';
                }, 600);
            }
        });
    }, {
        threshold: 0.08,
        rootMargin: '0px 0px -30px 0px'
    });

    revealTargets.forEach(el => observer.observe(el));
}

/* ==========================================================================
   3. Horizontal Slide-In (mono-tags, badges — fire-once via IntersectionObserver)
   ========================================================================== */
function initHorizontalSlideIns() {
    // Only apply to elements NOT already being handled by revealAnimations
    const slideLeftEls  = document.querySelectorAll('.mono-tag:not(.reveal-pending)');
    const slideRightEls = document.querySelectorAll('.slide-in-right');

    slideLeftEls.forEach(el => el.classList.add('h-slide', 'h-slide-left'));
    slideRightEls.forEach(el => el.classList.add('h-slide', 'h-slide-right'));

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('h-slide-visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15 });

    document.querySelectorAll('.h-slide').forEach(el => observer.observe(el));
}

/* ==========================================================================
   4. Counter Roll-Up Animations (Numbers count up on scroll)
   ========================================================================== */
function initCounterRollups() {
    const counters = document.querySelectorAll('[data-counter], .counter-rollup');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !entry.target.dataset.counted) {
                entry.target.dataset.counted = 'true';
                animateCounter(entry.target);
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.4 });

    counters.forEach(el => observer.observe(el));
}

function animateCounter(el) {
    const target   = parseInt(el.dataset.counter || el.textContent.replace(/[^\d]/g, ''), 10);
    const suffix   = el.dataset.suffix || '';
    const prefix   = el.dataset.prefix || '';
    const duration = 1800;
    const start    = performance.now();

    function update(now) {
        const elapsed  = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased    = 1 - Math.pow(2, -10 * progress); // easeOutExpo
        el.textContent = `${prefix}${Math.round(target * eased)}${suffix}`;
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

/* ==========================================================================
   5. Ambient Particle Canvas (Living Motion Trail)
   ========================================================================== */
function initAmbientParticleCanvas() {
    const canvas = document.getElementById('ambient-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width  = (canvas.width  = window.innerWidth);
    let height = (canvas.height = window.innerHeight);
    let mouse  = { x: -1000, y: -1000, radius: 150 };

    window.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
    window.addEventListener('mouseleave', () => { mouse.x = -1000; mouse.y = -1000; });
    window.addEventListener('resize', () => {
        width  = canvas.width  = window.innerWidth;
        height = canvas.height = window.innerHeight;
    });

    const particleCount = Math.min(Math.max(50, Math.floor((width * height) / 18000)), 80);
    const particles = [];

    class Particle {
        constructor() { this.reset(); }
        reset() {
            this.x          = Math.random() * width;
            this.y          = Math.random() * height;
            this.vx         = (Math.random() - 0.5) * 0.3;
            this.vy         = (Math.random() - 0.5) * 0.3;
            this.radius     = Math.random() * 2.2 + 1.0;
            this.baseAlpha  = Math.random() * 0.35 + 0.15;
            this.alpha      = this.baseAlpha;
            this.pulseSpeed = Math.random() * 0.022 + 0.008;
            this.pulseOffset= Math.random() * Math.PI * 2;
        }
        update(time) {
            this.y  -= globalScrollVelocity * 0.15;
            this.x  += this.vx;
            this.y  += this.vy;
            if (this.x < 0) this.x = width;
            if (this.x > width) this.x = 0;
            if (this.y < 0) this.y = ((this.y % height) + height) % height;
            if (this.y > height) this.y = this.y % height;
            this.alpha = this.baseAlpha + Math.sin(time * this.pulseSpeed + this.pulseOffset) * 0.12;

            const dx   = this.x - mouse.x;
            const dy   = this.y - mouse.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < mouse.radius) {
                const force = (mouse.radius - dist) / mouse.radius;
                const angle = Math.atan2(dy, dx);
                this.x += Math.cos(angle) * force * 2.0;
                this.y += Math.sin(angle) * force * 2.0;
            }
        }
        draw() {
            const stretch = Math.max(1, Math.min(Math.abs(globalScrollVelocity) * 0.6, 8));
            ctx.beginPath();
            if (stretch > 2.5) {
                ctx.moveTo(this.x, this.y);
                ctx.lineTo(this.x, this.y + (globalScrollVelocity > 0 ? stretch * 1.6 : -stretch * 1.6));
                ctx.strokeStyle = `rgba(212,246,235,${Math.min(1, this.alpha * 1.3)})`;
                ctx.lineWidth = this.radius * 0.85;
                ctx.stroke();
            } else {
                ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(212,246,235,${Math.max(0.05, this.alpha)})`;
                ctx.shadowBlur  = 9;
                ctx.shadowColor = 'rgba(159,227,206,0.45)';
                ctx.fill();
                ctx.shadowBlur  = 0;
            }
        }
    }

    for (let i = 0; i < particleCount; i++) particles.push(new Particle());

    let time = 0;
    function render() {
        time++;
        if (canvas.width !== window.innerWidth || canvas.height !== window.innerHeight) {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
        }
        ctx.clearRect(0, 0, width, height);

        // Constellation lines
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx   = particles[i].x - particles[j].x;
                const dy   = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 115) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(159,227,206,${(1 - dist / 115) * 0.12})`;
                    ctx.lineWidth = 0.7;
                    ctx.stroke();
                }
            }
        }

        particles.forEach(p => { p.update(time); p.draw(); });
        requestAnimationFrame(render);
    }
    render();
}

/* ==========================================================================
   6. Card Interactive Spotlight (Mouse-follow radial gradient)
   ========================================================================== */
function initAmbientSpotlight() {
    document.querySelectorAll('.card').forEach(card => {
        card.addEventListener('mousemove', e => {
            const rect = card.getBoundingClientRect();
            card.style.setProperty('--mouse-x', `${e.clientX - rect.left}px`);
            card.style.setProperty('--mouse-y', `${e.clientY - rect.top}px`);
        });
        card.addEventListener('mouseleave', () => {
            card.style.setProperty('--mouse-x', '-1000px');
            card.style.setProperty('--mouse-y', '-1000px');
        });
    });
}

/* ==========================================================================
   7. Modals & Dialog Handlers
   ========================================================================== */
function initModals() {
    document.querySelectorAll('[data-close-modal]').forEach(btn => {
        btn.addEventListener('click', e => {
            const modal = e.target.closest('.modal-overlay');
            if (modal) modal.classList.remove('active');
        });
    });

    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', e => {
            if (e.target === overlay) overlay.classList.remove('active');
        });
    });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
        }
    });
}

function toggleUsage(bookingId, action) {
    const isStart = action === 'start';
    const msg = isStart 
        ? "Konfirmasi: Mulai menggunakan ruangan ini sekarang?" 
        : "Konfirmasi: Selesai menggunakan ruangan ini sekarang?";
    
    if (!confirm(msg)) return;

    const endpoint = isStart 
        ? `/api/bookings/${bookingId}/start-use` 
        : `/api/bookings/${bookingId}/finish-use`;

    fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(r => r.json())
    .then(data => {
        alert(data.message);
        if (data.success) {
            window.location.reload();
        }
    })
    .catch(err => {
        console.error(err);
        alert('Terjadi kesalahan saat menghubungi server.');
    });
}

function openCheckInModal(bookingId, roomName) {
    toggleUsage(bookingId, 'start');
}

function submitCheckIn() {
    const bookingId = document.getElementById('modalBookingId')?.value;
    if (bookingId) toggleUsage(bookingId, 'start');
}

function confirmComing(bookingId) {
    if (!confirm("Confirming you are on your way will extend your QR check-in window by +15 minutes. Proceed?")) return;

    fetch(`/api/bookings/${bookingId}/confirm-coming`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(r => r.json())
    .then(data => { alert(data.message); window.location.reload(); })
    .catch(err => console.error(err));
}

function openExtensionModal(bookingId) {
    const modal = document.getElementById('extensionModal');
    if (!modal) return;
    document.getElementById('extBookingId').value = bookingId;
    modal.classList.add('active');
}

function submitExtension() {
    const bookingId = document.getElementById('extBookingId').value;
    const minutes   = document.getElementById('extMinutesSelect').value;

    fetch(`/api/bookings/${bookingId}/extend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ extra_minutes: minutes })
    })
    .then(r => r.json())
    .then(data => { alert(data.message); window.location.reload(); })
    .catch(err => console.error(err));
}

function handleApproval(bookingId, action) {
    let reason = '';
    if (action === 'REJECT') {
        reason = prompt("Please enter a brief reason for declining this request:") || "Time conflict or administrative choice";
    }

    fetch(`/api/approvals/${bookingId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, reason })
    })
    .then(r => r.json())
    .then(data => { alert(data.message); window.location.reload(); })
    .catch(err => console.error(err));
}
