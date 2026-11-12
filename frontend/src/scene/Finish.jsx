import { Bloom, EffectComposer, Noise, Vignette } from '@react-three/postprocessing'

// Three finishing touches, as on film, shared by every film on the site.
// Glow: only light brighter than full white bleeds, and only what the story
// follows is that bright. Grain: a trace of noise, so the dark is not flat.
// Vignette: the corners fall away slightly, which draws the eye to the middle.
export default function Finish() {
  return (
    <EffectComposer multisampling={4}>
      <Bloom mipmapBlur luminanceThreshold={1} luminanceSmoothing={0.1} intensity={0.85} radius={0.78} />
      <Noise premultiply opacity={0.22} />
      <Vignette offset={0.32} darkness={0.62} />
    </EffectComposer>
  )
}
