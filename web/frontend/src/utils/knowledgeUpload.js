/** 知识库上传文件类型（与后端 upload_types.py 一致） */

export const UPLOAD_ACCEPT =
  ".txt,.md,.markdown,.mdx,.pdf,.html,.htm,.xlsx,.xls,.docx,.csv,.json";

export const UPLOAD_EXTENSIONS = [
  "txt",
  "md",
  "markdown",
  "mdx",
  "pdf",
  "html",
  "htm",
  "xlsx",
  "xls",
  "docx",
  "csv",
  "json",
];

export const UPLOAD_HINT =
  "已支持 TXT、MARKDOWN、MDX、PDF、HTML、XLSX、XLS、DOCX、CSV、MD、HTM、JSON，每个文件不超过 50MB。";

export function isAllowedUploadFile(file) {
  const ext = (file.name.split(".").pop() || "").toLowerCase();
  return UPLOAD_EXTENSIONS.includes(ext);
}

export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

export function validateUploadFileSize(file) {
  return !file || file.size <= MAX_UPLOAD_BYTES;
}
