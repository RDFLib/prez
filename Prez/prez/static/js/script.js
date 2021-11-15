// breakpoints (px)
const smBreakpoint = 375;

// sizing
const sidenavWidth = "200px";
const sidenavWidthMobile = "80%";
const altWidthMobile = "80%";

// on page load
document.addEventListener("DOMContentLoaded", () => {
    const nav = document.querySelector("#main-nav-side");
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
        const hasSideNav = localStorage.getItem("hasSideNav") === "true";

        const nav = document.querySelector("#main-nav-side");

        if (isMobile) {
            if (navOpen) {
                nav.style.width = "0px";
            } else {
                nav.style.width = sidenavWidthMobile;
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

        const alt = document.querySelector("#content-col-sidebar");

        if (isMobile) {
            if (altOpen) {
                alt.style.width = "0px";
            } else {
                alt.style.width = altWidthMobile;
            }
            localStorage.setItem("altOpen", !altOpen);
        }
    }
});

// window resize
window.onresize = () => {
    const hasSideNav = localStorage.getItem("hasSideNav") === "true";

    const nav = document.querySelector("#main-nav-side");
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

        if (alt) {
            alt.style.width = "unset";
        }

        if (hasSideNav) {
            nav.style.width = sidenavWidth;
            nav.style.minWidth = sidenavWidth;
            localStorage.setItem("navOpen", true);
        } else {
            nav.style.width = "auto";
            localStorage.setItem("navOpen", true);
        }
    }
}

// on scrolling
document.onscroll = () => {
    const mobileHeader = document.querySelector("#mobile-header");
    const mobileTitle = document.querySelector("#mobile-title");
    const nav = document.querySelector("#main-nav-side");
    const alt = document.querySelector("#content-col-sidebar");
    const isMobile = localStorage.getItem("isMobile") === "true";

    if (isMobile) {
        if (window.scrollY >= mobileHeader.offsetTop) {
            console.log("top");
            nav.style.top = `${mobileHeader.offsetTop + 35}px`;
            nav.style.height = `calc(100vh - 35px)`;
            if (alt) {
                alt.style.top = `${mobileHeader.offsetTop + 35}px`;
                alt.style.height = `calc(100vh - 35px)`;
            }
    
            mobileTitle.style.display = "block";
        } else {
            nav.style.top = "unset";
            nav.style.height = `calc(100vh + ${window.scrollY}px - ${mobileHeader.offsetTop}px - 35px)`;
            if (alt) {
                alt.style.top = "unset";
                alt.style.height = `calc(100vh + ${window.scrollY}px - ${mobileHeader.offsetTop}px - 35px)`;
            }
    
            mobileTitle.style.display = "none";
        }
    }
}