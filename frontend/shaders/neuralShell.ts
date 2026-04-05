/** Neural Shell — barycentric edge detection + intelligence pulse wave */
export const shellVertex = /* glsl */ `
attribute vec3 aBarycentric;
uniform float uTime; uniform float uPulseAmp; uniform float uWaveFreq;
varying vec3 vBary; varying float vPulse;
void main(){
  vBary=aBarycentric;
  float dist=length(position);
  float wave=sin(dist*uWaveFreq-uTime*2.0);
  vPulse=smoothstep(-0.3,1.0,wave)*uPulseAmp;
  vec3 displaced=position+normal*vPulse*0.12;
  gl_Position=projectionMatrix*modelViewMatrix*vec4(displaced,1.0);
}`

export const shellFragment = /* glsl */ `
uniform vec3 uColor; uniform float uBaseAlpha;
varying vec3 vBary; varying float vPulse;
void main(){
  float edge=min(vBary.x,min(vBary.y,vBary.z));
  float w=0.02*(1.0+vPulse*5.0);
  float e=1.0-smoothstep(w,w+0.012,edge);
  if(e<0.01)discard;
  vec3 c=uColor*(1.0+vPulse*2.5);
  gl_FragColor=vec4(c,e*(uBaseAlpha+vPulse*0.7));
}`
