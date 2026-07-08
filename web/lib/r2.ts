import {
  S3Client,
  GetObjectCommand,
  ListObjectsV2Command,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

const BUCKET = process.env.R2_BUCKET!;

export const s3 = new S3Client({
  region: "auto",
  endpoint: process.env.R2_ENDPOINT,
  credentials: {
    accessKeyId: process.env.R2_ACCESS_KEY_ID!,
    secretAccessKey: process.env.R2_SECRET_ACCESS_KEY!,
  },
});

export async function presignPdf(docId: string): Promise<string> {
  return getSignedUrl(
    s3,
    new GetObjectCommand({
      Bucket: BUCKET,
      Key: `docs/${docId}.pdf`,
      ResponseContentType: "application/pdf",
      ResponseContentDisposition: "inline",
    }),
    { expiresIn: 6 * 3600 }
  );
}

// Cached set of downloaded doc ids (the R2 bucket is the "downloaded" flag).
let _set: Set<string> | null = null;
let _ts = 0;

export async function r2Set(): Promise<Set<string>> {
  if (_set && Date.now() - _ts < 5 * 60 * 1000) return _set;
  const ids = new Set<string>();
  let token: string | undefined;
  do {
    const r = await s3.send(
      new ListObjectsV2Command({
        Bucket: BUCKET,
        Prefix: "docs/",
        MaxKeys: 1000,
        ContinuationToken: token,
      })
    );
    for (const o of r.Contents ?? []) {
      const k = o.Key ?? "";
      if (k.endsWith(".pdf")) {
        const d = k.slice(5, -4);
        if (/^\d+$/.test(d)) ids.add(d);
      }
    }
    token = r.IsTruncated ? r.NextContinuationToken : undefined;
  } while (token);
  _set = ids;
  _ts = Date.now();
  return ids;
}
