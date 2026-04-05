import { mkdir, writeFile } from "fs/promises";
import path from "path";

export async function persistUpload(file: File) {
  const buffer = Buffer.from(await file.arrayBuffer());
  const uploadDir = process.env.UPLOAD_DIR ?? "./public/uploads";
  const targetDir = path.resolve(process.cwd(), uploadDir);
  const timestamp = Date.now();
  const safeName = file.name.replace(/\s+/g, "-").toLowerCase();
  const fileName = `${timestamp}-${safeName}`;

  await mkdir(targetDir, { recursive: true });
  await writeFile(path.join(targetDir, fileName), buffer);

  return {
    fileName,
    fileUrl: `/uploads/${fileName}`
  };
}
