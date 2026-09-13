// Client-side JavaScript for EduReserve Campus Portal
// Inspired by why.zero.university aesthetics & unitedcarriers.com scroll-driven physics

document.addEventListener('DOMContentLoaded', () => {
    initModals();
    initAmbientSpotlight();
    initAmbientParticleCanvas();
    initScrollPhysics();
    initScrollScrubAnimations();
    initCounterRollups();
    initSmoothTextReveals();
    initHorizontalSlideIns();
    initSectionParallax();
});

/* ==========================================================================
   1. Real-Time Scroll Physics, Velocity Engine & HUD Telemetry
   ========================================================================== */
let globalScrollVelocity = 0;
let globalScrollProgress = 0;

function initScrollPhysics() {
    const progressBar = document.getElementById('scroll-progress-bar');
    const hudVelocity = document.getElementById('hud-velocity');
    const hudProgress = document.getElementById('hud-progress');
    const hudElement = document.getElementById('scroll-telemetry');
    const navWrapper = document.getElementById('navbar-wrapper');
    const cards = document.querySelectorAll('.card');
    const bgGradient = document.getElementById('bg-gradient');

    let lastScrollY = window.scrollY;
    let lastTime = performance.now();
    let smoothVelocity = 0;
    let scrollDelta = 0;

    function onScrollFrame(currentTime) {
        const currentScrollY = window.scrollY;
        const maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
        const scrollPercent = Math.min(100, Math.max(0, (currentScrollY / maxScroll) * 100));
        globalScrollProgress = scrollPercent;

        // Top progress bar update
        if (progressBar) {
            progressBar.style.transform = `scaleX(${scrollPercent / 100})`;
        }

        // Velocity computation (px per second)
        const dt = Math.max(10, currentTime - lastTime);
        scrollDelta = currentScrollY - lastScrollY;
        const rawVelocity = Math.abs(scrollDelta) / (dt / 1000);
        
        // Smooth exponential dampening
        smoothVelocity = smoothVelocity * 0.82 + rawVelocity * 0.18;
        globalScrollVelocity = scrollDelta * 0.35;

        // Update HUD Telemetry
        if (hudVelocity) {
            hudVelocity.innerText = Math.round(smoothVelocity).toString().padStart(2, '0');
        }
        if (hudProgress) {
            hudProgress.innerText = `${Math.round(scrollPercent)}%`;
        }

        // Active scrolling aura on HUD
        if (hudElement) {
            if (smoothVelocity > 25) {
                hudElement.style.borderColor = 'var(--border-glow)';
                hudElement.style.boxShadow = '0 20px 45px -8px rgba(0, 0, 0, 0.65), 0 0 25px rgba(159, 227, 206, 0.3)';
            } else {
                hudElement.style.borderColor = 'var(--border-card)';
                hudElement.style.boxShadow = '0 16px 36px -8px rgba(0, 0, 0, 0.55)';
            }
        }

        // Sticky Navbar shrink & morph on scroll
        if (navWrapper) {
            if (currentScrollY > 40) {
                navWrapper.classList.add('scrolled');
            } else {
                navWrapper.classList.remove('scrolled');
            }
        }

        // 3D Inertia Tilt on Cards (Physical momentum during scroll)
        const tiltX = Math.max(-4.5, Math.min(4.5, scrollDelta * 0.12));

        cards.forEach((card, index) => {
            const cardOffset = (index % 2 === 0 ? 1 : -1) * Math.min(scrollDelta * 0.04, 3);
            if (smoothVelocity > 10) {
                card.style.transform = `perspective(1000px) rotateX(${-tiltX}deg) translateY(${cardOffset}px)`;
            } else {
                card.style.transform = `perspective(1000px) rotateX(0deg) translateY(0px)`;
            }
        });

        // Parallax depth on ambient background gradient (clamped so it never leaves the viewport)
        if (bgGradient) {
            const maxOffset = 45;
            const parallaxY = Math.max(-maxOffset, Math.min(maxOffset, currentScrollY * -0.012));
            bgGradient.style.transform = `translate3d(0, ${parallaxY}px, 0)`;
        }


        lastScrollY = currentScrollY;
        lastTime = currentTime;

        requestAnimationFrame(onScrollFrame);
    }

    requestAnimationFrame(onScrollFrame);
}

/* ==========================================================================
   2. Scroll-Scrubbed Animations (United Carriers Core Mechanic)
   Elements animate proportionally to their scroll position in the viewport.
   ========================================================================== */
function initScrollScrubAnimations() {
    // Scrubbed reveals: elements animate based on how far they've scrolled
    // into view, not just a binary appear/disappear
    const scrubElements = document.querySelectorAll('.card, .spacious-hero, .prompt-banner, footer, .scroll-scrub');
    
    scrubElements.forEach(el => {
        el.classList.add('scrub-target');
    });

    function updateScrub() {
        const windowH = window.innerHeight;
        
        document.querySelectorAll('.scrub-target').forEach((el, index) => {
            const rect = el.getBoundingClientRect();
            
            // Calculate how far the element is through the viewport
            // 0 = just entering bottom, 1 = fully in view, >1 = past center
            const enterProgress = Math.max(0, Math.min(1, 
                (windowH - rect.top) / (windowH * 0.75)
            ));
            
            // Smooth easing function for natural motion
            const eased = easeOutExpo(enterProgress);
            
            // Apply scroll-scrubbed transforms
            const translateY = (1 - eased) * 60; // Slides up 60px
            const opacity = eased;
            const scale = 0.92 + (eased * 0.08); // 0.92 -> 1.0
            
            // Stagger: alternate cards slide from left/right
            const slideX = (index % 2 === 0 ? -1 : 1) * (1 - eased) * 25;
            
            // Apply the scrubbed transform (only if element hasn't been manually transformed)
            if (!el.dataset.manualTransform) {
                el.style.opacity = opacity;
                el.style.transform = `translate3d(${slideX}px, ${translateY}px, 0) scale(${scale})`;
            }
            
            // Add revealed class for CSS hooks
            if (enterProgress > 0.3) {
                el.classList.add('revealed');
            }
        });

        requestAnimationFrame(updateScrub);
    }

    requestAnimationFrame(updateScrub);
}

// Easing functions for natural scroll-driven motion
function easeOutExpo(x) {
    return x === 1 ? 1 : 1 - Math.pow(2, -10 * x);
}

function easeOutCubic(x) {
    return 1 - Math.pow(1 - x, 3);
}

function easeInOutQuart(x) {
    return x < 0.5 ? 8 * x * x * x * x : 1 - Math.pow(-2 * x + 2, 4) / 2;
}

/* ==========================================================================
   3. Smooth Text Reveal Animations (Clip-path word reveals on scroll)
   Like unitedcarriers.com hero text that reveals word by word
   ========================================================================== */
function initSmoothTextReveals() {
    // Find all hero titles and apply per-word reveal
    const heroTitles = document.querySelectorAll('.spacious-hero-title, .text-reveal-target');
    
    heroTitles.forEach(title => {
        // Split text into words, wrapping each in a span
        const originalHTML = title.innerHTML;
        
        // Only process if not already processed
        if (title.dataset.revealed) return;
        title.dataset.revealed = 'true';
        
        // Wrap words in reveal containers
        const words = title.innerHTML.split(/(\s+)/);
        title.innerHTML = words.map((word, i) => {
            if (word.trim() === '') return word;
            // Keep HTML tags intact
            if (word.startsWith('<')) return word;
            return `<span class="word-reveal-wrap"><span class="word-reveal" style="transition-delay: ${i * 0.06}s">${word}</span></span>`;
        }).join('');
    });

    // Observe when titles enter viewport
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('words-visible');
            }
        });
    }, {
        threshold: 0.15,
        rootMargin: '0px 0px -60px 0px'
    });

    heroTitles.forEach(el => observer.observe(el));
}

/* ==========================================================================
   4. Counter Roll-Up Animations (Numbers count up on scroll)
   Like unitedcarriers.com statistics that roll up when scrolled into view
   ========================================================================== */
function initCounterRollups() {
    const counters = document.querySelectorAll('[data-counter], .counter-rollup');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !entry.target.dataset.counted) {
                entry.target.dataset.counted = 'true';
                animateCounter(entry.target);
            }
        });
    }, {
        threshold: 0.4
    });

    counters.forEach(el => observer.observe(el));
}

function animateCounter(el) {
    const target = parseInt(el.dataset.counter || el.textContent.replace(/[^\d]/g, ''), 10);
    const suffix = el.dataset.suffix || '';
    const prefix = el.dataset.prefix || '';
    const duration = 1800;
    const start = performance.now();
    
    function update(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = easeOutExpo(progress);
        const current = Math.round(target * eased);
        
        el.textContent = `${prefix}${current}${suffix}`;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

/* ==========================================================================
   5. Horizontal Slide-In Elements (Scroll-driven lateral motion)
   Elements slide in from left/right as user scrolls
   ========================================================================== */
function initHorizontalSlideIns() {
    const slideLeftEls = document.querySelectorAll('.slide-in-left, .mono-tag');
    const slideRightEls = document.querySelectorAll('.slide-in-right, .badge');
    
    // Apply initial states
    slideLeftEls.forEach(el => {
        if (!el.classList.contains('scrub-target')) {
            el.classList.add('h-slide', 'h-slide-left');
        }
    });
    
    slideRightEls.forEach(el => {
        if (!el.classList.contains('scrub-target')) {
            el.classList.add('h-slide', 'h-slide-right');
        }
    });

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('h-slide-visible');
            }
        });
    }, {
        threshold: 0.2,
        rootMargin: '0px 0px -30px 0px'
    });

    document.querySelectorAll('.h-slide').forEach(el => observer.observe(el));
}

/* ==========================================================================
   6. Section Parallax (Multi-depth parallax layers on scroll)
   ========================================================================== */
function initSectionParallax() {
    const parallaxElements = document.querySelectorAll('.parallax-slow, .parallax-fast, .card-icon, .spacious-hero');
    
    if (parallaxElements.length === 0) return;

    function updateParallax() {
        const scrollY = window.scrollY;
        
        parallaxElements.forEach(el => {
            const rect = el.getBoundingClientRect();
            const centerY = rect.top + rect.height / 2;
            const viewportCenter = window.innerHeight / 2;
            const offset = (centerY - viewportCenter) / window.innerHeight;
            
            if (el.classList.contains('parallax-slow')) {
                el.style.transform = `translateY(${offset * -20}px)`;
            } else if (el.classList.contains('parallax-fast')) {
                el.style.transform = `translateY(${offset * -45}px)`;
            } else if (el.classList.contains('card-icon')) {
                // Subtle floating effect on card icons
                const float = Math.sin(scrollY * 0.003 + parseInt(el.closest('.card')?.dataset.index || 0)) * 4;
                el.style.transform = `translateY(${float}px) rotate(${offset * 3}deg)`;
            }
        });

        requestAnimationFrame(updateParallax);
    }

    requestAnimationFrame(updateParallax);
    
    // Index cards for staggered float effect
    document.querySelectorAll('.card').forEach((card, i) => {
        card.dataset.index = i;
    });
}

/* ==========================================================================
   7. Interactive Particle & Scroll-Warp Canvas (Living Motion Trail)
   ========================================================================== */
function initAmbientParticleCanvas() {
    const canvas = document.getElementById('ambient-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    let mouse = { x: -1000, y: -1000, radius: 150 };

    window.addEventListener('mousemove', (e) => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    });

    window.addEventListener('mouseleave', () => {
        mouse.x = -1000;
        mouse.y = -1000;
    });

    window.addEventListener('resize', () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    });

    const particleCount = Math.min(Math.max(65, Math.floor((width * height) / 16000)), 90);
    const particles = [];

    class Particle {
        constructor() {
            this.reset();
        }

        reset() {
            this.x = Math.random() * width;
            this.y = Math.random() * height;
            this.vx = (Math.random() - 0.5) * 0.35;
            this.vy = (Math.random() - 0.5) * 0.35;
            this.radius = Math.random() * 2.2 + 1.1;
            this.baseAlpha = Math.random() * 0.4 + 0.2;
            this.alpha = this.baseAlpha;
            this.pulseSpeed = Math.random() * 0.025 + 0.01;
            this.pulseOffset = Math.random() * Math.PI * 2;
        }

        update(time, scrollPush) {
            // Smooth inertia scroll response
            this.y -= scrollPush * 0.18;
            this.x += this.vx;
            this.y += this.vy;

            // Seamless infinite wrap around viewport boundaries so screen is always filled
            if (this.x < 0) this.x = width;
            if (this.x > width) this.x = 0;
            if (this.y < 0) this.y = ((this.y % height) + height) % height;
            if (this.y > height) this.y = this.y % height;

            // Breathing pulse
            this.alpha = this.baseAlpha + Math.sin(time * this.pulseSpeed + this.pulseOffset) * 0.14;

            // Cursor interactive repulsion
            const dx = this.x - mouse.x;
            const dy = this.y - mouse.y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < mouse.radius) {
                const force = (mouse.radius - dist) / mouse.radius;
                const angle = Math.atan2(dy, dx);
                this.x += Math.cos(angle) * force * 2.2;
                this.y += Math.sin(angle) * force * 2.2;
            }
        }

        draw(scrollPush) {
            ctx.beginPath();
            const stretch = Math.max(1, Math.min(Math.abs(scrollPush) * 0.6, 10));

            if (stretch > 2.2) {
                // Motion blur trail line during fast scroll
                ctx.moveTo(this.x, this.y);
                ctx.lineTo(this.x, this.y + (scrollPush > 0 ? stretch * 1.8 : -stretch * 1.8));
                ctx.strokeStyle = `rgba(212, 246, 235, ${Math.min(1, this.alpha * 1.4)})`;
                ctx.lineWidth = this.radius * 0.9;
                ctx.stroke();
            } else {
                // Crisp circular luminescent orb
                ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(212, 246, 235, ${Math.max(0.05, this.alpha)})`;
                ctx.shadowBlur = 10;
                ctx.shadowColor = 'rgba(159, 227, 206, 0.5)';
                ctx.fill();
                ctx.shadowBlur = 0;
            }
        }
    }

    for (let i = 0; i < particleCount; i++) {
        particles.push(new Particle());
    }

    let time = 0;
    function render() {
        time++;
        
        // Ensure canvas stays perfectly fitted to viewport
        if (canvas.width !== window.innerWidth || canvas.height !== window.innerHeight) {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
        }

        ctx.clearRect(0, 0, width, height);

        const currentPush = globalScrollVelocity;

        // Draw connective constellations
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 120) {
                    const lineAlpha = (1 - dist / 120) * 0.14;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(159, 227, 206, ${lineAlpha})`;
                    ctx.lineWidth = 0.75;
                    ctx.stroke();
                }
            }
        }

        particles.forEach(p => {
            p.update(time, currentPush);
            p.draw(currentPush);
        });

        requestAnimationFrame(render);
    }


    render();
}

/* ==========================================================================
   8. Dynamic Card Spotlight Tracking
   ========================================================================== */
function initAmbientSpotlight() {
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            card.style.setProperty('--mouse-x', `${x}px`);
            card.style.setProperty('--mouse-y', `${y}px`);
        });

        card.addEventListener('mouseleave', () => {
            card.style.setProperty('--mouse-x', `-1000px`);
            card.style.setProperty('--mouse-y', `-1000px`);
        });
    });
}

/* ==========================================================================
   9. Modals & Dialog Handlers
   ========================================================================== */
function initModals() {
    document.querySelectorAll('[data-close-modal]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const modal = e.target.closest('.modal-overlay');
            if (modal) modal.classList.remove('active');
        });
    });

    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('active');
            }
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
        }
    });
}

function openCheckInModal(bookingId, roomName) {
    const modal = document.getElementById('qrCheckInModal');
    if (!modal) return;
    
    document.getElementById('modalBookingId').value = bookingId;
    document.getElementById('modalRoomTitle').innerText = roomName;
    const pinInput = document.getElementById('modalPinInput');
    pinInput.value = '';
    modal.classList.add('active');
    setTimeout(() => pinInput.focus(), 150);
}

function submitCheckIn() {
    const bookingId = document.getElementById('modalBookingId').value;
    const pin = document.getElementById('modalPinInput').value;

    if (!pin) {
        alert('Please enter the 4-digit Room PIN displayed on the room door placard.');
        return;
    }

    fetch(`/api/bookings/${bookingId}/check-in`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: pin })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            window.location.reload();
        } else {
            alert(data.message);
        }
    })
    .catch(err => {
        console.error(err);
        alert('Error communicating with server.');
    });
}

function confirmComing(bookingId) {
    if (!confirm("Confirming you are on your way will extend your QR check-in window by +15 minutes (total 30 mins max). Proceed?")) return;

    fetch(`/api/bookings/${bookingId}/confirm-coming`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        window.location.reload();
    })
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
    const minutes = document.getElementById('extMinutesSelect').value;

    fetch(`/api/bookings/${bookingId}/extend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ extra_minutes: minutes })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        window.location.reload();
    })
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
        body: JSON.stringify({ action: action, reason: reason })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        window.location.reload();
    })
    .catch(err => console.error(err));
}
