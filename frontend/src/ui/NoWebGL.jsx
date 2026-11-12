// What a visitor sees when the browser can't draw 3D graphics at all (WebGL is
// switched off, or the device doesn't have it). Without this they would get an
// empty dark page and no idea why.
export default function NoWebGL() {
  return (
    <div className="app">
      <header className="top"><span className="mark">RAG Galaxy</span></header>
      <section className="caption on">
        <div>
          <h2>This film needs 3D graphics.</h2>
          <p className="caption-body">
            RAG Galaxy is a short interactive film about how an AI looks things up before it answers, and it is
            drawn in 3D. This browser has 3D graphics (WebGL) switched off or unavailable. Try a current version
            of Chrome, Safari, Firefox or Edge, or turn on hardware acceleration in this browser’s settings.
          </p>
          <a className="caption-link" href="https://github.com/sxnfer/rag-galaxy">
            Read about it on GitHub
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
          </a>
        </div>
      </section>
    </div>
  )
}
