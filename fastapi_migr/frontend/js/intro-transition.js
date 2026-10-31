(() => {
    const intro = document.getElementById("airfarex-intro");
    const aircraft = intro?.querySelector(".airfarex-intro-aircraft");
    if (!intro || !aircraft) return;

    let finished = false;
    const finishIntro = () => {
        if (finished) return;
        finished = true;
        intro.classList.add("is-leaving");
        window.setTimeout(() => intro.remove(), 750);
    };

    // Reveal the real dashboard after the aircraft completes its bottom-left
    // to top-right flight. The timeout is a fallback for animation interruptions.
    aircraft.addEventListener("animationend", finishIntro, { once: true });
    window.setTimeout(finishIntro, 5200);
})();
