import { useEffect, useState } from "react";

type Props = {
  src: string;
  alt?: string;
  className?: string;
  expiredClassName?: string;
  expiredMessage?: string;
};

const DEFAULT_EXPIRED =
  "이미지가 만료되었거나 로드할 수 없습니다 — AI로 다시 생성하거나 영구 저장(R2)을 설정하세요.";

export function PreviewHttpsImage({
  src,
  alt = "",
  className,
  expiredClassName,
  expiredMessage = DEFAULT_EXPIRED,
}: Props) {
  const [broken, setBroken] = useState(false);

  useEffect(() => {
    setBroken(false);
  }, [src]);

  if (!src.startsWith("https://")) return null;
  if (broken) {
    return <p className={expiredClassName ?? "text-xs text-amber-300/90"}>{expiredMessage}</p>;
  }
  return (
    <img
      src={src}
      alt={alt}
      className={className}
      referrerPolicy="no-referrer"
      onError={() => setBroken(true)}
    />
  );
}
