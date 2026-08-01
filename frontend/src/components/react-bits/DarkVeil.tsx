export function DarkVeil() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_8%,rgba(199,215,122,0.10),transparent_24rem),linear-gradient(180deg,#171711,#11120f_58%,#191913)]" />
      <div className="rb-tactical-grid absolute inset-0 opacity-75" />
      <div className="absolute inset-x-0 top-0 h-px bg-primary/30" />
      <div className="absolute bottom-0 left-0 right-0 h-40 bg-[linear-gradient(180deg,transparent,rgba(17,18,15,0.88))]" />
    </div>
  );
}
