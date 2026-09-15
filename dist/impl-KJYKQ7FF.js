import {createRequire as __createRequire} from 'module';var require=__createRequire(import.meta.url);
import{a as M}from"./chunk-MM37US67.js";import{d as C}from"./chunk-ORMEAYYY.js";import"./chunk-VWK56BXR.js";import{a as T}from"./chunk-TSNRSQX3.js";import{a as j,b as $,c as x,d as S}from"./chunk-ASJLJZK4.js";import"./chunk-WDR26R2W.js";import"./chunk-2PLXYHUG.js";import{b as d,c as y,e as b,f as _,g as A,h as p,i as E,j as l,l as k,r as f,t as v}from"./chunk-GBMHU7PM.js";import{h as m}from"./chunk-AE6O5N6J.js";var N=`name: Compile

# This job triggers when opening/updating a pull request or merging to the main branch
on:
  pull_request:
    types: [opened, synchronize, reopened]
  push:
    branches: [main]

concurrency:
  group: \${{ github.workflow }}-\${{ github.head_ref && github.ref || github.run_id }}
  cancel-in-progress: \${{ github.event_name == 'pull_request' }}

env:
  # You can pin a particular version by replacing latest. E.g., @gamemaker/gm-cli@1.0.2
  GM_COMMAND: "@gamemaker/gm-cli@latest"

jobs:
  compile:
    runs-on: ubuntu-latest

    steps:
      # Check out the git branch to build against
      - name: Checkout
        uses: actions/checkout@v6

      # Save a cache that can be reused between runs.
      # This will future runs faster, just like when you build the game locally
      - name: Cache
        uses: actions/cache@v5
        with:
          path: .gmcache
          key: \${{ runner.os }}-gmcache

      # ffmpeg is needed for linux: https://github.com/YoYoGames/GameMaker-Bugs/issues/4977
      - name: Load cached FFmpeg
        if: \${{ runner.os == 'Linux' }}
        id: cache-ffmpeg
        uses: actions/cache@v5
        with:
          path: ~/.local/share/ffmpeg-bin
          key: \${{ runner.os }}-ffmpeg-6.0.1

      - name: Install FFmpeg if not cached
        if: \${{ runner.os == 'Linux' && steps.cache-ffmpeg.outputs.cache-hit != 'true' }}
        run: |
          VERSION=6.0.1
          RELEASE_NAME=ffmpeg-\${VERSION}-amd64-static
          mkdir -p ~/.local/share/ffmpeg-bin
          wget --timeout=8 --tries=10 https://www.johnvansickle.com/ffmpeg/old-releases/\${RELEASE_NAME}.tar.xz
          tar -xf \${RELEASE_NAME}.tar.xz
          mv \${RELEASE_NAME}/ffmpeg \${RELEASE_NAME}/ffprobe ~/.local/share/ffmpeg-bin/
          rm -rf \${RELEASE_NAME} \${RELEASE_NAME}.tar.xz

      # Make sure the cached binaries are available to subsequent steps
      - name: Add FFmpeg to PATH
        if: \${{ runner.os == 'Linux' }}
        run: echo "$HOME/.local/share/ffmpeg-bin" >> $GITHUB_PATH

      # You can create an access token at https://gamemaker.io/en/account/access-keys
      # Then, in github, set a Repository Secret named GAMEMAKER_PAT with that value
      # in you repository Settings/Secrets and Varibles/Actions/New repository secret
      - run: npx "$GM_COMMAND" login "$GAMEMAKER_PAT"
        if: \${{ env.GAMEMAKER_PAT != '' }}

      # "Test compile" the game. Does not produce a bundle, but rather checks that it
      # possible to compile the game
      - run: npx "$GM_COMMAND" compile
        env:
          NO_COLOR: 1
`;var G=`name: Package
# This jobs start when the user trigger it manually from Github repository/Actions
on: [workflow_dispatch]

env:
  GAME_NAME: "{{GAME_NAME}}"
  # You can pin a particular version by replacing latest. E.g., @gamemaker/gm-cli@1.0.2
  GM_COMMAND: "@gamemaker/gm-cli@latest"

jobs:
  compile:
    strategy:
      matrix:
        # Select any runner and targets you want to build with
        # runner: The machine that builds your game. See https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job
        # target: The platform the game will run on.
        include:
          - runner: ubuntu-latest
            target: operagx
          # - runner: ubuntu-latest
          #   target: linux
          # - runner: ubuntu-latest
          #   target: windows
          # - runner: macos-latest
          #   target: mac
    runs-on: \${{ matrix.runner }}

    steps:
      # Check out the git branch to build against
      - name: Checkout
        uses: actions/checkout@v6

      # Save a cache that can be reused between runs.
      # This will future runs faster, just like when you build the game locally
      - name: Cache
        uses: actions/cache@v5
        with:
          path: .gmcache
          key: \${{ runner.os }}-gmcache-\${{ matrix.target }}

      # ffmpeg is needed for linux: https://github.com/YoYoGames/GameMaker-Bugs/issues/4977
      - name: Load cached FFmpeg
        if: \${{ runner.os == 'Linux' }}
        id: cache-ffmpeg
        uses: actions/cache@v5
        with:
          path: ~/.local/share/ffmpeg-bin
          key: \${{ runner.os }}-ffmpeg-6.0.1

      - name: Install FFmpeg if not cached
        if: \${{ runner.os == 'Linux' && steps.cache-ffmpeg.outputs.cache-hit != 'true' }}
        run: |
          VERSION=6.0.1
          RELEASE_NAME=ffmpeg-\${VERSION}-amd64-static
          mkdir -p ~/.local/share/ffmpeg-bin
          wget --timeout=8 --tries=10 https://www.johnvansickle.com/ffmpeg/old-releases/\${RELEASE_NAME}.tar.xz
          tar -xf \${RELEASE_NAME}.tar.xz
          mv \${RELEASE_NAME}/ffmpeg \${RELEASE_NAME}/ffprobe ~/.local/share/ffmpeg-bin/
          rm -rf \${RELEASE_NAME} \${RELEASE_NAME}.tar.xz

      # Make sure the cached binaries are available to subsequent steps
      - name: Add FFmpeg to PATH
        if: \${{ runner.os == 'Linux' }}
        run: echo "$HOME/.local/share/ffmpeg-bin" >> $GITHUB_PATH

      # You can create an access token at https://gamemaker.io/en/account/access-keys
      # Then, in github, set a Repository Secret named GAMEMAKER_PAT with that value
      # in you repository Settings/Secrets and Varibles/Actions/New repository secret
      - run: npx "$GM_COMMAND" login "$GAMEMAKER_PAT"
        if: \${{ env.GAMEMAKER_PAT != '' }}

      # Build and package the game. Create a file called package.zip.
      - run: npx "$GM_COMMAND" package --target \${{ matrix.target }} --output ./package.zip
        env:
          NO_COLOR: 1

      # Create the final name on the format \`name-target-commit.zip\` For example \`spacerocks-windows-5e0179f.zip\`
      - name: Create artifact name
        run: echo "ARTIFACT_NAME=\${GAME_NAME}-\${{ matrix.target }}-\${GITHUB_SHA::7}.zip" >> $GITHUB_ENV

      # Upload the game. You can then find it in you github repo under Actions/<The workflow run>/Artifacts
      - uses: actions/upload-artifact@v7
        with:
          name: \${{ env.ARTIFACT_NAME }}
          path: ./package.zip
`;var P=`
# Windows

# Windows thumbnail cache files
Thumbs.db
Thumbs.db:encryptable
ehthumbs.db
ehthumbs_vista.db

# Dump file
*.stackdump

# Folder config file
[Dd]esktop.ini

# Recycle Bin used on file shares
$RECYCLE.BIN/

# Windows Installer files
*.cab
*.msi
*.msix
*.msm
*.msp

# Windows shortcuts
*.lnk

# Mac

## General
.DS_Store
.AppleDouble
.LSOverride

## Icon must end with two \r
Icon

## Thumbnails
._*

## Files that might appear in the root of a volume
.DocumentRevisions-V100
.fseventsd
.Spotlight-V100
.TemporaryItems
.Trashes
.VolumeIcon.icns
.com.apple.timemachine.donotpresent

## Directories potentially created on remote AFP share
.AppleDB
.AppleDesktop
Network Trash Folder
Temporary Items
.apdisk

# GameMaker temporary files
*.resource_order
*.old

# GMRT build directory
Build
`,R=`
# Ignore .yy files for language statistics
*.yy linguist-generated=true

# force LF for metadata files for merge simplicity
*.gml text eol=lf
*.yy text eol=lf
*.yyp text eol=lf
*.json text eol=lf
`;function L(){return N}function F(e){return G.replace("{{GAME_NAME}}",e.name)}async function D(e){let r=await e.fetch("https://api.gamemaker.io/api/gamemaker/project-templates");if(!r.ok)throw new m(`Failed to fetch templates: ${r.statusText}`);return[...(await r.json()).data.map(({id:i,attributes:o})=>o.gml_code_download_url?{kind:"download",description:o.info_description,downloadUrl:o.gml_code_download_url,id:i,title:o.info_title,type:o.project_type_name}:null).filter(i=>!!i),{kind:"blank",id:"blank",title:"Blank Game",description:"An empty project",type:"Game"}]}function u(e){if(!e)return"Project name is required";if(!/^[a-z0-9-_]+$/i.test(e))return"Use only letters, numbers, dashes, and underscores"}function g(e,r){return e.find(t=>t.id===r)??e.find(t=>t.title.toLowerCase().includes(r.toLowerCase()))}async function I(e,r){b("Create a GameMaker project");let t=await y({projectName:()=>E({message:"What's your project name?",placeholder:"my-awesome-game",defaultValue:e.name,validate:a=>u(a??"")}),projectType:async()=>{let a=[...new Set(r.map(i=>i.type))].sort();return p({message:"What type of project?",options:a.map(i=>({value:i,label:i}))})},template:async({results:a})=>{let i=r.filter(({type:o})=>o===a.projectType).sort((o,s)=>o.title.localeCompare(s.title));return p({message:"Pick a template",options:i.map(({id:o,title:s})=>({value:o,label:s.replace(/ Template$/,"").replace(/ Live Wallpaper$/,"").replace(/ Game Strip$/,"")}))})},toolchain:()=>p({message:"Toolchain",options:[{value:{type:"GMS2"},label:"GMS2"},{value:{type:"GMRT"},label:"GMRT (Experimental)"}]}),useAi:()=>d({message:"Set up AI scaffolding (MCP, CLAUDE.md, etc.)",initialValue:e.ai??!0}),useActions:()=>d({message:"Set up GitHub Actions workflows",initialValue:e.actions??!0})},{onCancel:()=>{process.exit(0)}});return{projectName:t.projectName,template:t.template,useAi:t.useAi,useActions:t.useActions,toolchain:t.toolchain}}async function O(e,r,t,a){let i=await B(e,r.downloadUrl),o=await f(e,i)??await H(e,i);if(!o)throw await e.fs.rm(i,{recursive:!0}),new m("Invariant broken: Template archive does not contain a .yyp project file");let s=await j(e,a,l,{verbose:!1}),{gmpmDllPath:n}=await $(e,a,l,{verbose:!1}),c=await x(e,a,l,{verbose:!1}),h=await S(e,a,l,{projectToolPath:s,projectPath:o,packageToolPath:c,gmpmDllPath:n,verbose:!0}),Y=e.path.join(t.dir,`${t.name}.yyp`);e.child_process.execFileSync(s,["PROJECT","SAVE",`SOURCE=${o}`,`DESTINATION=${Y}`,`PREFABSFOLDER=${h}`],{env:e.process.platform==="darwin"?{...e.process.env,COMPlus_ZapDisable:"1"}:void 0}),await e.fs.rm(i,{recursive:!0})}async function B(e,r){let t=await e.fetch(r);if(!t.ok)throw new m(`Failed to download template: ${t.statusText}`);let a=new Uint8Array(await t.arrayBuffer()),i=await new Promise((s,n)=>{T(a,(c,h)=>{c?n(c):s(h)})}),o=await e.fs.mkdtemp(e.path.join(e.os.tmpdir(),"gm-scaffold-"));for(let[s,n]of Object.entries(i)){if(s.endsWith("/"))continue;let c=e.path.join(o,s);await e.fs.mkdir(e.path.dirname(c),{recursive:!0}),await e.fs.writeFile(c,n)}return o}async function H(e,r){let t=await e.fs.readdir(r);for(let a of t){let i=e.path.join(r,a);try{let o=await f(e,i);if(o)return o}catch{}}}var w='# Editing GameMaker project files\n\nDo not make changes to `.yy` or `.yyp` files yourself.\nIt\'s very hard to correctly edit these manually!\nYou MUST use commands exposed by the `gamemaker-resource-tool` MCP server.\n\n# GameMaker Language (GML) Guidance\n\nMake changes to `.gml` files using your built-in tools, if you so wish.\n\n## GML Naming conventions\n\n- Use `snake_case` for all variables and functions\n- Prefix local variables with `_` (e.g., `var _temp_value`, `var _effect`)\n- Prefix resource names based on their type, e.g. obj_player, spr_player, etc.\n\n## GML reserved names\n\nYour own names must avoid clashing with these:\n\n- `score`, `lives`, `health`\n- Position: `x`, `y`\n- Sprite: `sprite_index`, `image_index`, `image_speed`, `image_xscale`, `image_yscale`, `image_angle`, `image_alpha`, `image_blend`\n- Physics: `speed`, `direction`, `friction`, `gravity`, `gravity_direction`\n- Collision: `bbox_left`, `bbox_right`, `bbox_top`, `bbox_bottom`\n- Instance: `id`, `object_index`, `layer`, `depth`, `visible`, `persistent`\n\n## Modern idiomatic GML\n\nGML has support for **structs** (dynamic objects similar to JavaScript).\n\n```gml\nvar _mystruct =\n{\n    a : 20,\n    b : "Hello World"\n};\n\n// There is support for constructor functions and methods tied to the struct too\nfunction Vector2(_x, _y) constructor\n{\n    x = _x;\n    y = _y;\n\n    static Add = function(_vec2)\n    {\n        x += _vec2.x;\n        y += _vec2.y;\n    }\n}\n\nv2 = new Vector2(10, 10);\n```\n\nGML *script* files now requires one or more function definitions\n\n```gml\n// in move script\nfunction move(spd, dir)\n{\n    speed = spd;\n    direction = dir;\n}\n\n```\n\n## Library Functions\n\n- Prefer `instance_create_layer()` over deprecated `instance_create()`\n\n# Running / debugging games\n\nTo help users debug and play games you can make use of:\n\n```\nnpx @gamemaker/gm-cli compile --errors-only\nnpx @gamemaker/gm-cli run --errors-only\n```\n';async function ke(e){let r=await D(this),t;if(e.interactive)t=await I({name:e.name,ai:e.ai,actions:e.actions},r);else{if(!e.name)throw new m("--name is required in non-interactive mode");if(!e.template)throw new m("--template is required in non-interactive mode");let n=u(e.name);if(n)throw new m(n);let c=g(r,e.template);if(!c)throw new m(`Template "${e.template}" not found`);t={projectName:e.name,template:c.id,useAi:e.ai,useActions:e.actions,toolchain:e.toolchain??{type:"GMS2"}},this.process.stdout.write(`Creating project...
`)}let a=this.path.join(this.process.cwd(),t.projectName);if(await k(this,a))throw new m(`Directory "${t.projectName}" already exists`);let i=g(r,t.template);if(!i)throw new Error(`Template "${t.template}" not found`);let o=A(),s=await v.initLazy(this,e.cacheDir?{type:"absolute",path:e.cacheDir}:{type:"infer",projectDir:a});try{if(i.kind==="blank"?(o.start("Creating blank project"),await this.fs.mkdir(a,{recursive:!0}),await M(this,{ignoreStdio:!0,run:{mode:"command",command:`project create name="${t.projectName}" path="${a}"`}})):(o.start("Downloading template"),o.message("Extracting template"),await O(this,i,{name:t.projectName,dir:a},s)),o.message("Creating base files"),await this.fs.writeFile(this.path.join(a,".gitignore"),P),await this.fs.writeFile(this.path.join(a,".gitattributes"),R),t.useAi){await this.fs.writeFile(this.path.join(a,"CLAUDE.md"),w),await this.fs.writeFile(this.path.join(a,"AGENTS.md"),w);let n=this.path.join(a,".claude");await this.fs.mkdir(n,{recursive:!0}),await this.fs.writeFile(this.path.join(n,"settings.local.json"),JSON.stringify({permissions:{allow:["mcp__gamemaker-resource-tool"],deny:["Edit(*.yy)","Edit(*.yyp)"]},enabledMcpjsonServers:["gamemaker-resource-tool"],enableAllProjectMcpServers:!0},null,2)+`
`);let c=this.process.platform==="win32";await this.fs.writeFile(this.path.join(a,".mcp.json"),JSON.stringify({mcpServers:{"gamemaker-resource-tool":{type:"stdio",...c?{command:"cmd",args:["/c","npx @gamemaker/gm-cli@latest resourcetool mcp"]}:{command:"npx",args:["@gamemaker/gm-cli@latest","resourcetool","mcp"]},env:{}}}},null,2)+`
`)}if(t.useActions){let n=this.path.join(a,".github","workflows");await this.fs.mkdir(n,{recursive:!0}),await this.fs.writeFile(this.path.join(n,"compile.yml"),L()),await this.fs.writeFile(this.path.join(n,"package.yml"),F({name:t.projectName}))}await C(this,s,a,{toolchain:t.toolchain}),o.stop(`Project created at ${a}`),e.interactive&&_("Project created!")}catch(n){throw o.stop("Failed"),n}}export{ke as default};
