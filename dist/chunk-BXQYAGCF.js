import {createRequire as __createRequire} from 'module';var require=__createRequire(import.meta.url);
import{s as v}from"./chunk-XRKG2QD3.js";import{f as k,g as d,h as c}from"./chunk-AE6O5N6J.js";import Q from"node:crypto";var R="gxe-gamemaker-cli";var D="https://oauth2.opera-api.com",T=["https://api.gx.games/gamedev:write","https://api.gx.games/gamedev:read"].join("+"),A="gxgames-link",U="gxgames-auth",q="https://api.gx.games";var j="auth.json",z=d.object({accessToken:d.string(),expiresAt:d.number(),refreshToken:d.string().optional()}),w=class{constructor(e,t){this.ctx=e;this.projectDir=t}async read(){let e=await this.cacheDir();try{let t=await this.ctx.fs.readFile(this.ctx.path.join(e,j),"utf-8");return z.parse(JSON.parse(t))}catch{return}}async write(e){let t=await this.cacheDir();await this.ctx.fs.writeFile(this.ctx.path.join(t,j),JSON.stringify(e,null,2))}async cacheDir(){return(await v.initLazy(this.ctx,{type:"infer",projectDir:this.projectDir})).getSubDirPath(this.ctx,U,{preferShared:!0})}};var F=`<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GX.games \u2014 Authenticated</title>
    <style>
      * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }

      body {
        background: #050305;
        color: #e8e8e8;
        font-family: "Segoe UI", system-ui, sans-serif;
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
      }

      .card {
        background: #111011;
        border: 1px solid #222022;
        border-top: 3px solid #6b7ff7;
        border-radius: 6px;
        padding: 40px 48px;
        max-width: 380px;
        width: 90%;
      }

      h1 {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 8px;
      }

      p {
        font-size: 0.875rem;
        color: #888;
        line-height: 1.6;
      }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Authentication successful</h1>
      <p>
        You're signed in to GX.games. You can close this tab and return to the
        terminal.
      </p>
    </div>
  </body>
</html>
`;var x=`<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GX.games \u2014 Authentication Failed</title>
    <style>
      * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }

      body {
        background: #050305;
        color: #e8e8e8;
        font-family: "Segoe UI", system-ui, sans-serif;
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
      }

      .card {
        background: #111011;
        border: 1px solid #222022;
        border-top: 3px solid #6b7ff7;
        border-radius: 6px;
        padding: 40px 48px;
        max-width: 380px;
        width: 90%;
      }

      h1 {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 8px;
      }

      p {
        font-size: 0.875rem;
        color: #888;
        line-height: 1.6;
        margin-bottom: 16px;
      }

      .error-detail {
        background: #050305;
        border: 1px solid #222022;
        border-radius: 4px;
        padding: 10px 14px;
        font-family: "Consolas", "Courier New", monospace;
        font-size: 0.8rem;
        color: #aaa;
        word-break: break-word;
      }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Authentication failed</h1>
      <p>Something went wrong. You can close this tab and try again.</p>
      <div class="error-detail">{{ERROR_MESSAGE}}</div>
    </div>
  </body>
</html>
`;var E=class{constructor(e){this.config=e;this.baseUrl=e.baseUrl??D,this.redirectPort=e.redirectPort??53784,this.redirectUri=`http://localhost:${String(this.redirectPort)}/`}baseUrl;redirectPort;redirectUri;async exchangeToken(e){let t=await this.config.fetch(new URL("/oauth2/v1/token/",this.baseUrl),{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams({...e,client_id:R}).toString()+`&scope=${T}`});if(!t.ok){let a=await t.json().catch(()=>null);throw new c(`Token exchange failed: ${a?.error??t.statusText}`)}let r=await t.json();if(!r.access_token)throw new c("No access_token in response");return{accessToken:r.access_token,expiresAt:Date.now()+((r.expires_in??3600)-60)*1e3,refreshToken:r.refresh_token}}async browserAuth(){let e=Q.randomBytes(16).toString("hex"),t=new URL("/oauth2/v1/authorize/",this.baseUrl);t.search=new URLSearchParams({response_type:"code",client_id:R,redirect_uri:this.redirectUri,state:e}).toString()+`&scope=${T}`;let r=new Promise((s,g)=>{let y=this.config.http.createServer((u,m)=>{let p=new URL(u.url??"/",this.redirectUri),l=p.searchParams.get("code"),f=p.searchParams.get("state"),n=p.searchParams.get("error_description")??p.searchParams.get("error");if(m.writeHead(200,{"Content-Type":"text/html"}),y.close(),f!==e){let i="State mismatch";m.end(x.replace("{{ERROR_MESSAGE}}",i)),g(new c(i))}else if(l)s({code:l,sendPage:i=>m.end(i)});else{let i=n??"No auth code in redirect";m.end(x.replace("{{ERROR_MESSAGE}}",i)),g(new c(i))}});y.on("error",g),y.listen(this.redirectPort)}),a=t.toString();await this.config.open(a);let h=this.config.makeTaskLogger("Authenticating");h.message(`Opening ${k.blue.underline(a)}`);let{code:P,sendPage:_}=await r;try{let s=await this.exchangeToken({grant_type:"authorization_code",code:P,redirect_uri:this.redirectUri});return _(F),h.success("Authenticated"),s}catch(s){throw _(x.replace("{{ERROR_MESSAGE}}",s instanceof Error?s.message:String(s))),s}}async getAccessToken(){let e=await this.config.storage.read();if(e&&e.expiresAt>Date.now())return e.accessToken;if(e?.refreshToken)try{let r=await this.exchangeToken({grant_type:"refresh_token",refresh_token:e.refreshToken});return await this.config.storage.write(r),r.accessToken}catch{}let t=await this.browserAuth();return await this.config.storage.write(t),t.accessToken}};function ne(o,e){return new E({fetch:o.fetch,http:o.http,open:o.open,makeTaskLogger:o.makeTaskLogger,storage:new w(o,e)})}var O="link.json",J=d.object({studioId:d.string(),gameId:d.string()}),S=class{constructor(e,t){this.ctx=e;this.projectDir=t}async read(){let e=await this.cacheDir();try{let t=await this.ctx.fs.readFile(this.ctx.path.join(e,O),"utf-8");return J.parse(JSON.parse(t))}catch{throw new c("Game not linked. Run `gm-cli gxgames link --studioid <studio> --gameid <game>` first.")}}async write(e){let t=await this.cacheDir();await this.ctx.fs.writeFile(this.ctx.path.join(t,O),JSON.stringify(e,null,2))}async cacheDir(){return(await v.initLazy(this.ctx,{type:"infer",projectDir:this.projectDir})).getSubDirPath(this.ctx,A)}};var I={age_rating_not_set:"age rating needed to publish the public track",asset_not_found:"asset not found",aws_upload_error:"failed uploading the file to S3",breaking_published_game:"game is published and this operation would break requirements for publication",bundle_must_be_zip:"only zip files are allowed for game bundles",cover_not_found:"cover not found",game_access_denied:"game access denied",game_bundle_too_big:"game bundle exceeds the maximum size",game_bundle_unsupported_charset:"game bundle was encoded with an unsupported charset",game_cover_not_found:"cover id not valid or not found for provided gameId",game_creation_not_allowed:"only the owner of the group may create a game for the group",game_description_empty:"short description needed to publish the public track",game_engine_not_found:"game engine not found",game_is_blocked:"game is currently blocked",game_name_empty:"a game name is required",game_name_taken:"name already in use by another game",game_name_too_long:"game name too long",game_not_found:"game id not valid or game not visible to user",game_update_not_allowed:"user doesn't have the rights for updating game",gms_runner_version_deprecated:"selected GMS runner version is deprecated",gms_runner_version_not_found:"GMS runner not found",gms_runner_version_required:"GMS runner version is required",image_invalid_aspect_ratio:"the image has an invalid aspect ratio",image_too_small:"the image is too small",internal_server_error:"internal server error",invalid_characters_in_name:"name contains one or more invalid characters",invalid_image:"image validation failed",invalid_request_payload:"validation error in payload request",invalid_studio_ownership:"the users studio has an invalid amount of owners (not 1)",max_games_limit_reached:"the group has reached its max games limit",max_graphics_limit_reached:"the game has reached the maximum number of graphics per game limit",missing_game_covers:"must have a cover uploaded for all supported aspect ratios",missing_index_file:"uploaded bundle is missing the file index.html",no_changes:"the request resulted in no changes",no_graphics_uploaded:"at least 1 graphic needed to publish the public track",no_platforms_added:"at least one platform needed to publish the public track",no_release_for_track:"no releases on the selected track",no_specific_studio_for_user:"The user doesn't have a specific studio",page_invalid:"invalid page parameter value; must be a valid decimal integer",page_less_than_0:"invalid page parameter value; must be 0 or higher",page_size_invalid:"invalid pageSize parameter value; must be a valid decimal integer",page_size_less_than_1:"invalid pageSize parameter value; must be 1 or higher",page_size_too_high:"the page size exceeds the maximum limit",preview_required_for_videos:"when uploading videos, a 'preview' image must be included as a thumbnail",shared_array_buffer_is_not_supported:"Shared Array buffer support is not provided",short_description_too_long:"short description too long",sign_in_required:"the user must be signed in",sign_up_not_completed:"user has not completed the sign-up process",studio_access_denied:"studio access denied",studio_not_found:"studio id not valid",template_metadata_required_for_template:"games in the HH Store should have template metadata",unsupported_graphic_format:"the image format is not supported or could not be identified",upload_custom_game_bundle_not_allowed:"upload custom game bundle not allowed",version_number_too_low:"version number is lower than previous version",video_not_allowed_as_image:"not allowed to use video as image"};var C=class{baseUrl="";securityData=null;securityWorker;abortControllers=new Map;customFetch=(...e)=>fetch(...e);baseApiParams={credentials:"same-origin",headers:{},redirect:"follow",referrerPolicy:"no-referrer"};constructor(e={}){Object.assign(this,e)}setSecurityData=e=>{this.securityData=e};encodeQueryParam(e,t){return`${encodeURIComponent(e)}=${encodeURIComponent(typeof t=="number"?t:`${t}`)}`}addQueryParam(e,t){return this.encodeQueryParam(t,e[t])}addArrayQueryParam(e,t){return e[t].map(a=>this.encodeQueryParam(t,a)).join("&")}toQueryString(e){let t=e||{};return Object.keys(t).filter(a=>typeof t[a]<"u").map(a=>Array.isArray(t[a])?this.addArrayQueryParam(t,a):this.addQueryParam(t,a)).join("&")}addQueryParams(e){let t=this.toQueryString(e);return t?`?${t}`:""}contentFormatters={["application/json"]:e=>e!==null&&(typeof e=="object"||typeof e=="string")?JSON.stringify(e):e,["application/vnd.api+json"]:e=>e!==null&&(typeof e=="object"||typeof e=="string")?JSON.stringify(e):e,["text/plain"]:e=>e!==null&&typeof e!="string"?JSON.stringify(e):e,["multipart/form-data"]:e=>e instanceof FormData?e:Object.keys(e||{}).reduce((t,r)=>{let a=e[r];return t.append(r,a instanceof Blob?a:typeof a=="object"&&a!==null?JSON.stringify(a):`${a}`),t},new FormData),["application/x-www-form-urlencoded"]:e=>this.toQueryString(e)};mergeRequestParams(e,t){return{...this.baseApiParams,...e,...t||{},headers:{...this.baseApiParams.headers||{},...e.headers||{},...t&&t.headers||{}}}}createAbortSignal=e=>{if(this.abortControllers.has(e)){let r=this.abortControllers.get(e);return r?r.signal:void 0}let t=new AbortController;return this.abortControllers.set(e,t),t.signal};abortRequest=e=>{let t=this.abortControllers.get(e);t&&(t.abort(),this.abortControllers.delete(e))};request=async({body:e,secure:t,path:r,type:a,query:h,format:P,baseUrl:_,cancelToken:s,...g})=>{let y=(typeof t=="boolean"?t:this.baseApiParams.secure)&&this.securityWorker&&await this.securityWorker(this.securityData)||{},u=this.mergeRequestParams(g,y),m=h&&this.toQueryString(h),p=this.contentFormatters[a||"application/json"],l=P||u.format;return this.customFetch(`${_||this.baseUrl||""}${r}${m?`?${m}`:""}`,{...u,headers:{...u.headers||{},...a&&a!=="multipart/form-data"?{"Content-Type":a}:{}},signal:(s?this.createAbortSignal(s):u.signal)||null,body:typeof e>"u"||e===null?null:p(e)}).then(async f=>{let n=f;n.data=null,n.error=null;let i=l?f.clone():f,L=l?await i[l]().then(b=>(n.ok?n.data=b:n.error=b,n)).catch(b=>(n.error=b,n)):n;return s&&this.abortControllers.delete(s),L})};unwrap=async e=>{let t=await e;return t.error?{success:!1,errors:t.error.errors.map(({code:r})=>({code:r,description:I[r]}))}:{success:!0,data:t.data.data}}};var G=class extends C{createGame=(e,t={})=>this.unwrap(this.request({path:"/gamedev/games",method:"POST",body:e,secure:!0,type:"application/json",format:"json",...t}));deleteCover=(e,t,r={})=>this.unwrap(this.request({path:`/gamedev/games/${e}/covers/${t}`,method:"DELETE",secure:!0,format:"json",...r}));deleteGraphic=(e,t,r={})=>this.unwrap(this.request({path:`/gamedev/games/${e}/graphics/${t}`,method:"DELETE",secure:!0,format:"json",...r}));getGameDetails=(e,t={})=>this.unwrap(this.request({path:`/gamedev/games/${e}`,method:"GET",secure:!0,format:"json",...t}));getProfile=(e={})=>this.unwrap(this.request({path:"/gamedev/profile",method:"GET",secure:!0,format:"json",...e}));getUserGames=(e,t={})=>this.unwrap(this.request({path:"/gamedev/games",method:"GET",query:e,secure:!0,format:"json",...t}));getUserStudios=(e,t={})=>this.unwrap(this.request({path:"/gamedev/studios",method:"GET",query:e,secure:!0,format:"json",...t}));publishGame=(e,t={})=>this.unwrap(this.request({path:`/gamedev/games/${e}/publish`,method:"POST",secure:!0,format:"json",...t}));updateGame=(e,t,r={})=>this.unwrap(this.request({path:`/gamedev/games/${e}`,method:"PATCH",body:t,secure:!0,type:"application/json",format:"json",...r}));uploadCover=(e,t,r,a={})=>this.unwrap(this.request({path:`/gamedev/games/${e}/covers`,method:"POST",query:t,body:r,secure:!0,type:"multipart/form-data",format:"json",...a}));uploadGameBundle=(e,t,r,a={})=>this.unwrap(this.request({path:`/gamedev/games/${e}/bundles`,method:"POST",query:t,body:r,secure:!0,type:"multipart/form-data",format:"json",...a}));uploadGraphic=(e,t,r={})=>this.unwrap(this.request({path:`/gamedev/games/${e}/graphics`,method:"POST",body:t,secure:!0,type:"multipart/form-data",format:"json",...r}))};var xe=o=>o.map(e=>e.description.slice(0,1).toUpperCase()+e.description.slice(1)).join(`.
`);function Ce(o,e){return new G({customFetch:o.fetch,baseUrl:q,securityWorker:async()=>({headers:{Authorization:`Bearer ${await e.getAccessToken()}`}})})}export{ne as a,S as b,xe as c,Ce as d};
