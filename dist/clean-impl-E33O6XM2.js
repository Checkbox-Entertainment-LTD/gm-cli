import {createRequire as __createRequire} from 'module';var require=__createRequire(import.meta.url);
import{g as s,h as i}from"./chunk-YJRH7NK4.js";import"./chunk-Y73HSQ25.js";import{f as o}from"./chunk-7YQV5RAR.js";async function r(t,a,e){if(t.process.stdout.write(o.bold(`${a}
`)),!e){t.process.stdout.write(`Skipped

`);return}t.process.stdout.write(`${e}
`),await t.fs.rm(e,{recursive:!0,force:!0}),t.process.stdout.write(`Cleaned

`)}async function d(t){i(t);let a=await s(this,t),e=await a._getInternalLocalPath(this),n=await a._getInternalSharedPath(this);await r(this,"Shared cache",n),await r(this,"Local cache",e)}export{d as default};
