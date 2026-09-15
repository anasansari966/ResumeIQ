import { useState } from "react";
import { templatePreviewSrc } from "../api";

/** Card thumbnail: always loads `/api/v1/templates/{id}/preview`; gradient fallback if the request fails. */
export default function TemplatePreviewThumb({ templateId, previewUrl, heightClass, fallbackClassName }) {
  const [broken, setBroken] = useState(false);
  const path =
    previewUrl && String(previewUrl).trim()
      ? String(previewUrl).trim()
      : `/api/v1/templates/${encodeURIComponent(templateId)}/preview`;
  const src = templatePreviewSrc(path);

  if (broken || !templateId) {
    return <div className={`${heightClass} w-full rounded-lg ${fallbackClassName || "bg-gradient-to-br from-teal-100 to-teal-200"}`} />;
  }

  return (
    <img
      src={src}
      alt=""
      className={`${heightClass} w-full object-cover object-top`}
      loading="lazy"
      decoding="async"
      onError={() => setBroken(true)}
    />
  );
}
