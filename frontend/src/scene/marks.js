import { BufferAttribute, BufferGeometry, Color, ShaderMaterial } from 'three'
import { INK } from './theme.js'

// Dots and thin lines for the two smaller films (the search, the journey).
//
// Unlike the library's thousand passages (Passages.jsx), these are few: a
// couple of hundred at most. So their places and brightness are simply worked
// out in JavaScript every frame and handed to the graphics card as lists.
//
// One number per dot or line end says how bright it is. Up to 1 it is how
// solid the ink is; anything over 1 is passed on as extra light, which the
// glow picks up (Finish.jsx).

const DOT_VERTEX = /* glsl */ `
  attribute float aLight;  // how bright
  attribute float aSize;   // how wide, in the scene's own units
  uniform float uPixels;
  varying float vLight;
  varying float vPixels;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = clamp(aSize * uPixels / max(0.1, -mv.z), 1.5, 90.0);
    vPixels = gl_PointSize;
    vLight = aLight;
    gl_Position = projectionMatrix * mv;
  }
`
const DOT_FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  varying float vLight;
  varying float vPixels;
  void main() {
    // A round dot with a clean edge, whatever its size.
    float r = length(gl_PointCoord - 0.5) * 2.0;
    float edge = clamp(2.5 / vPixels, 0.02, 0.9);
    float disc = 1.0 - smoothstep(1.0 - edge, 1.0, r);
    if (disc <= 0.0 || vLight <= 0.002) discard;
    gl_FragColor = vec4(uColor * max(1.0, vLight), min(1.0, vLight) * disc);
  }
`
const LINE_VERTEX = /* glsl */ `
  attribute float aLight;
  varying float vLight;
  void main() {
    vLight = aLight;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`
const LINE_FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  varying float vLight;
  void main() {
    if (vLight <= 0.002) discard;
    gl_FragColor = vec4(uColor * max(1.0, vLight), min(1.0, vLight));
  }
`

// Room for `count` dots. Fill `position`, `light` and `size`, then call touch().
export function makeDots(count) {
  const geometry = new BufferGeometry()
  const position = new Float32Array(count * 3), light = new Float32Array(count), size = new Float32Array(count)
  geometry.setAttribute('position', new BufferAttribute(position, 3))
  geometry.setAttribute('aLight', new BufferAttribute(light, 1))
  geometry.setAttribute('aSize', new BufferAttribute(size, 1))
  const material = new ShaderMaterial({
    vertexShader: DOT_VERTEX, fragmentShader: DOT_FRAGMENT, transparent: true, depthWrite: false, depthTest: false,
    uniforms: { uPixels: { value: 1000 }, uColor: { value: new Color(INK) } },
  })
  const touch = () => { for (const k of ['position', 'aLight', 'aSize']) geometry.getAttribute(k).needsUpdate = true }
  return { geometry, material, position, light, size, touch }
}

// Room for `count` straight lines. Each frame: begin(), then add(from, to, light) for every line, then end().
export function makeLines(count) {
  const geometry = new BufferGeometry()
  const position = new Float32Array(count * 6), light = new Float32Array(count * 2)
  geometry.setAttribute('position', new BufferAttribute(position, 3))
  geometry.setAttribute('aLight', new BufferAttribute(light, 1))
  const material = new ShaderMaterial({
    vertexShader: LINE_VERTEX, fragmentShader: LINE_FRAGMENT, transparent: true, depthWrite: false, depthTest: false,
    uniforms: { uColor: { value: new Color(INK) } },
  })
  let n = 0
  return {
    geometry, material,
    begin() { n = 0 },
    // A line from a to b. lightA and lightB let it fade along its length.
    add(a, b, lightA, lightB = lightA) {
      if (n >= count || (lightA <= 0.002 && lightB <= 0.002)) return
      position.set([a.x, a.y, a.z, b.x, b.y, b.z], n * 6)
      light[n * 2] = lightA; light[n * 2 + 1] = lightB
      n++
    },
    end() {
      geometry.setDrawRange(0, n * 2)
      geometry.getAttribute('position').needsUpdate = true
      geometry.getAttribute('aLight').needsUpdate = true
    },
  }
}
