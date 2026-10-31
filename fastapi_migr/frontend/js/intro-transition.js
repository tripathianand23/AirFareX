(() => {
    const intro = document.getElementById("airfarex-intro");
    if (!intro) return;

    let finished = false;

    const finishIntro = () => {
        if (finished) return;
        finished = true;
        intro.classList.add("is-leaving");

        window.setTimeout(() => {
            intro.remove();
        }, 1150);
    };

    // Preserve the intro loading transition without an aircraft animation.
    window.setTimeout(finishIntro, 5500);
})();
