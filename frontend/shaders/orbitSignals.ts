/** Orbit Signals — GPU-instanced elliptical orbits */
export const orbitVertex = /* glsl */ `
attribute vec3 aOrbitParams; attribute vec2 aOrbitSpeed;
uniform float uTime;
varying float vAlpha;
void main(){
  float Ra=aOrbitParams.x,Rb=aOrbitParams.y,phase=aOrbitParams.z;
  float speed=aOrbitSpeed.x,incl=aOrbitSpeed.y;
  float theta=uTime*speed+phase;
  vec3 orb; orb.x=Ra*cos(theta);
  float s=Rb*sin(theta); orb.y=s*sin(incl); orb.z=s*cos(incl);
  vec4 local=instanceMatrix*vec4(position,1.0);
  vec3 final=local.xyz+orb;
  vec4 mv=modelViewMatrix*vec4(final,1.0);
  gl_Position=projectionMatrix*mv;
  vAlpha=smoothstep(12.0,3.5,length(orb))*0.55;
}`

export const orbitFragment = /* glsl */ `
uniform vec3 uColor; varying float vAlpha;
void main(){ gl_FragColor=vec4(uColor,vAlpha); }`
