// If the visitor asked the system for less motion, stop the carousel autoplay.
document.addEventListener("DOMContentLoaded", function () {
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return;
  }
  const carousel = document.getElementById("heroCarousel");
  if (carousel && window.bootstrap) {
    const instance = window.bootstrap.Carousel.getOrCreateInstance(carousel);
    instance.pause();
    carousel.removeAttribute("data-bs-ride");
  }
});
