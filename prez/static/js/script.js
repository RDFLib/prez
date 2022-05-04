// breakpoints (px)
const smBreakpoint = 420;

// sizing
const sidenavWidth = "200px";
const sidenavWidthMobile = "80%";
const altWidthMobile = "80%";

// on page load
document.addEventListener("DOMContentLoaded", () => {
    const nav = document.querySelector("#main-nav");
    if (nav.classList.contains("colnav")) {
        localStorage.setItem("hasSideNav", true);
    } else {
        localStorage.setItem("hasSideNav", false);
    }

    if (window.innerWidth <= smBreakpoint) {
        localStorage.setItem("isMobile", true);
        localStorage.setItem("navOpen", false);
        localStorage.setItem("altOpen", false);

        const mobileHeader = document.querySelector("#mobile-header");
        const alt = document.querySelector("#content-col-sidebar");
        if (alt) {
            alt.style.height = `calc(97vh - ${mobileHeader.offsetTop}px)`;
        }
    } else {
        localStorage.setItem("isMobile", false);
        localStorage.setItem("navOpen", true);
        localStorage.setItem("altOpen", true);
    }
});

// nav toggler
const toggleBtn = document.querySelectorAll(".nav-toggle");
toggleBtn.forEach(btn => {
    btn.onclick = () => {
        const isMobile = localStorage.getItem("isMobile") === "true";
        const navOpen = localStorage.getItem("navOpen") === "true";
        const altOpen = localStorage.getItem("altOpen") === "true";
        const hasSideNav = localStorage.getItem("hasSideNav") === "true";

        const nav = document.querySelector("#main-nav");
        const lightbox = document.querySelector("#lightbox");
        const alt = document.querySelector("#content-col-sidebar");

        if (isMobile) {
            if (navOpen) {
                nav.style.width = "0px";
                lightbox.classList.remove("open");
            } else {
                if (altOpen) {
                    alt.style.width = "0px";
                    localStorage.setItem("altOpen", !altOpen);
                }
                nav.style.width = sidenavWidthMobile;
                lightbox.classList.add("open");
            }
        } else {
            if (hasSideNav) {
                if (navOpen) {
                    nav.style.minWidth = "0px";
                    nav.style.width = "0px";
                } else {
                    nav.style.minWidth = sidenavWidth;
                    nav.style.width = sidenavWidth;
                }
            }
        }

        localStorage.setItem("navOpen", !navOpen);
    }
});

// alt toggler
const altToggle = document.querySelectorAll(".alt-toggle");
altToggle.forEach(btn => {
    btn.onclick = () => {
        const isMobile = localStorage.getItem("isMobile") === "true";
        const altOpen = localStorage.getItem("altOpen") === "true";
        const navOpen = localStorage.getItem("navOpen") === "true";

        const alt = document.querySelector("#content-col-sidebar");
        const nav = document.querySelector("#main-nav");
        const lightbox = document.querySelector("#lightbox");

        if (isMobile) {
            if (altOpen) {
                alt.style.width = "0px";
                lightbox.classList.remove("open");
            } else {
                if (navOpen) {
                    nav.style.width = "0px";
                    localStorage.setItem("navOpen", !navOpen);
                }
                alt.style.width = altWidthMobile;
                lightbox.classList.add("open");
            }
            localStorage.setItem("altOpen", !altOpen);
        }
    }
});

// geom collapse toggler
const geomCollapseBtn = document.querySelectorAll(".geom-collapse-btn");
geomCollapseBtn.forEach(btn => {
    btn.onclick = () => {
        const geomString = btn.parentNode.parentNode.querySelector(".geom-string");
        if (geomString.classList.contains("collapse")) {
            geomString.classList.remove("collapse");
            btn.innerHTML = '<i class="far fa-minus"></i> Collapse';
        } else {
            geomString.classList.add("collapse");
            btn.innerHTML = '<i class="far fa-plus"></i> Expand';
        }
    }
});

// geom copy button
const geomCopyBtn = document.querySelectorAll(".geom-copy-btn");
geomCopyBtn.forEach(btn => {
    btn.onclick = () => {
        const geomString = btn.parentNode.parentNode.querySelector(".geom-string");
        navigator.clipboard.writeText(geomString.textContent.trim());
    }
});

// window resize
window.onresize = () => {
    const hasSideNav = localStorage.getItem("hasSideNav") === "true";

    const nav = document.querySelector("#main-nav");
    const lightbox = document.querySelector("#lightbox");
    const alt = document.querySelector("#content-col-sidebar");

    if (window.innerWidth <= smBreakpoint) {
        nav.style.width = "0px";
        nav.style.minWidth = "0px";
        if (alt) {
            const mobileHeader = document.querySelector("#mobile-header");
            alt.style.height = `calc(97vh - ${mobileHeader.offsetTop}px)`;
            alt.style.width = "0px";
        }

        localStorage.setItem("navOpen", false);
        localStorage.setItem("altOpen", false);
        localStorage.setItem("isMobile", true);
    } else {
        localStorage.setItem("isMobile", false);
        localStorage.setItem("altOpen", true);
        lightbox.classList.remove("open");

        if (alt) {
            alt.style.width = "unset";
            alt.style.height = "unset";
        }

        if (hasSideNav) {
            nav.style.width = sidenavWidth;
            nav.style.minWidth = sidenavWidth;
            localStorage.setItem("navOpen", true);
        } else {
            nav.style.width = "auto";
            nav.style.height = "unset";
            localStorage.setItem("navOpen", true);
        }
    }
}

// on scrolling
document.onscroll = () => {
    const mobileHeader = document.querySelector("#mobile-header");
    const mobileTitle = document.querySelector("#mobile-title");
    const nav = document.querySelector("#main-nav");
    const lightbox = document.querySelector("#lightbox");
    const alt = document.querySelector("#content-col-sidebar");
    const isMobile = localStorage.getItem("isMobile") === "true";

    if (isMobile) {
        if (window.scrollY >= mobileHeader.offsetTop) {
            nav.style.top = `${mobileHeader.offsetTop + 35}px`;
            nav.style.height = `calc(100vh - 35px)`;
            lightbox.style.top = `${mobileHeader.offsetTop + 35}px`;
            lightbox.style.height = `calc(100vh - 35px)`;
            if (alt) {
                alt.style.top = `${mobileHeader.offsetTop + 35}px`;
                alt.style.height = `calc(100vh - 35px)`;
            }

            mobileTitle.style.display = "block";
        } else {
            nav.style.top = "unset";
            nav.style.height = `calc(100vh + ${window.scrollY}px - ${mobileHeader.offsetTop}px - 35px)`;
            lightbox.style.top = "unset";
            lightbox.style.height = `calc(100vh + ${window.scrollY}px - ${mobileHeader.offsetTop}px - 35px)`;
            if (alt) {
                alt.style.top = "unset";
                alt.style.height = `calc(100vh + ${window.scrollY}px - ${mobileHeader.offsetTop}px - 35px)`;
            }

            mobileTitle.style.display = "none";
        }
    }
}

// toggle collapse narrower concepts
const conceptCollapse = document.querySelectorAll(".concept-collapse-btn");
conceptCollapse.forEach(btn => {
    btn.onclick = () => {
        btn.parentElement.nextElementSibling.classList.toggle("expand");
        btn.firstChild.classList.toggle("fa-minus");
        btn.firstChild.classList.toggle("fa-plus");
    }
});

// toggle expand all concepts
const expandAll = document.querySelector("#expand-all"); // errors when null
if (expandAll) {
    expandAll.onclick = () => {
        const conceptCollapse = document.querySelectorAll(".concept-collapse-btn");
        const narrower = document.querySelectorAll(".narrower");
        const icon = document.querySelector("#expand-all-icon");
        const text = document.querySelector("#expand-all-text");
    
        if (expandAll.classList.contains("expand")) {
            narrower.forEach(n => {
                n.classList.remove("expand");
            });
    
            conceptCollapse.forEach(btn => {
                btn.firstChild.classList.remove("fa-minus");
                btn.firstChild.classList.add("fa-plus");
            });
    
            icon.classList.remove("fa-minus");
            icon.classList.add("fa-plus");
    
            text.innerHTML = "Expand all";
        } else {
            narrower.forEach(n => {
                n.classList.add("expand");
            });
    
            conceptCollapse.forEach(btn => {
                btn.firstChild.classList.remove("fa-plus");
                btn.firstChild.classList.add("fa-minus");
            });
    
            icon.classList.remove("fa-plus");
            icon.classList.add("fa-minus");
            text.innerHTML = "Collapse all";
        }
    
        expandAll.classList.toggle("expand");
    };
}

// expand/collapse subnavs
