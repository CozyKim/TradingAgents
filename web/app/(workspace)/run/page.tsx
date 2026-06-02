import { Suspense } from "react";

import { RunForm } from "@/components/run/run-form";

export default function RunPage() {
  return (
    <div className="mx-auto w-full max-w-screen-md px-4 py-5 md:px-8 md:py-10">
      <header className="mb-6">
        <p className="text-[13px] font-semibold tracking-[-0.01em] text-text-3">
          새 분석 실행
        </p>
        <h1 className="display mt-1 text-[26px] leading-[1.2] text-text-1 md:text-[30px]">
          종목과 애널리스트를
          <br />
          골라주세요.
        </h1>
      </header>
      {/* RunForm이 useSearchParams를 쓰므로 정적 생성 시 Suspense 경계가 필요하다. */}
      <Suspense fallback={<p className="text-xs text-text-3">Loading…</p>}>
        <RunForm />
      </Suspense>
    </div>
  );
}
