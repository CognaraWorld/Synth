import { simplexNoise3D } from './noise'

/** Kernel particle swarm — noise displacement + intelligence pulse + cursor pull */
export const kernelVertex = /* glsl */ `
${simplexNoise3D}
attribute float aSize; attribute float aPhase;
uniform float uTime; uniform float uPulse; uniform float uPixelRatio; uniform vec2 uMouse;
varying float vAlpha;
void main(){
  vec3 pos=position; float dist=length(pos);
  vec3 dir=dist>0.001?pos/dist:vec3(0.,1.,0.);
  float n=snoise(pos*1.5+uTime*0.2)+snoise(pos*3.0+uTime*0.35)*0.4;
  pos+=dir*n*0.3*uPulse;
  pos+=dir*sin(dist*6.0-uTime*2.5+aPhase)*0.12*uPulse;
  vec2 toM=uMouse*3.0-pos.xy; float md=length(toM)+0.001;
  pos.xy+=(toM/md)*smoothstep(4.0,0.0,md)*0.18;
  vec4 mv=modelViewMatrix*vec4(pos,1.0);
  gl_PointSize=aSize*uPixelRatio*(200.0/-mv.z);
  gl_PointSize=clamp(gl_PointSize,0.5,35.0);
  gl_Position=projectionMatrix*mv;
  vAlpha=smoothstep(4.5,0.2,dist)*0.85;
}`

export const kernelFragment = /* glsl */ `
uniform vec3 uColor; varying float vAlpha;
void main(){
  float d=length(gl_PointCoord-0.5); if(d>0.5)discard;
  float soft=smoothstep(0.5,0.05,d); float bright=smoothstep(0.18,0.0,d);
  gl_FragColor=vec4(mix(uColor,vec3(1.0),bright*0.7),soft*vAlpha);
}`
