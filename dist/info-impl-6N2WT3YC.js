import {createRequire as __createRequire} from 'module';var require=__createRequire(import.meta.url);
import{g as n,h as a}from"./chunk-PY65RNZY.js";import"./chunk-I3LFMXD3.js";import{f as r}from"./chunk-7YQV5RAR.js";async function c(s,e){return(await s.fs.readdir(e,{withFileTypes:!0})).filter(t=>t.isDirectory()).map(t=>t.name).sort()}async function p(s){a(s);let e=await n(this,s),i=await e._getInternalLocalPath(this),t=await e._getInternalSharedPath(this);if(this.process.stdout.write(r.bold(`Shared cache
`)),this.process.stdout.write(`${t??"Not used when explicit --cache-dir is set"}
`),t){let o=await c(this,t);this.process.stdout.write(`Contents: ${o.join(", ")||"(none)"}
`)}if(this.process.stdout.write(`
`),this.process.stdout.write(r.bold(`Local cache
`)),this.process.stdout.write(`${i??"Not used. Specify a --project"}
`),i){let o=await c(this,i);this.process.stdout.write(`Contents: ${o.join(", ")||"(none)"}
`)}}export{p as default};
