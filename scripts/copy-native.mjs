import { mkdir, readdir, copyFile } from "node:fs/promises";
await mkdir("dist/native", { recursive: true });
for (const name of await readdir("native")) {
  if (name.endsWith(".py") && !name.startsWith("test_"))
    await copyFile("native/" + name, "dist/native/" + name);
}
