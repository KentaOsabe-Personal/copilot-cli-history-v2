import { Link, Outlet } from 'react-router'

function AppShell() {
  return (
    <div className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100">
      <div className="mx-auto flex max-w-5xl flex-col gap-8">
        <header className="rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-slate-950/40">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-sm font-medium text-cyan-200">
                Read-only viewer
              </div>
              <h1 className="mt-4 text-4xl font-semibold tracking-tight text-white md:text-5xl">
                Copilot CLI Session History
              </h1>
              <p className="mt-4 text-base leading-7 text-slate-300">
                この画面は閲覧専用です。
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                セッション一覧では日付範囲と検索語で絞り込めます。検索語は会話本文、preview、issue を対象にし、作業ディレクトリは検索結果の一覧タブで切り替えられます。repository / branch / model の専用フィルタ、編集、削除、共有、自動更新は提供しません。
              </p>
            </div>

            <nav aria-label="Primary" className="flex shrink-0 items-center">
              <Link
                to="/"
                className="inline-flex items-center rounded-full border border-cyan-400/40 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-400/20"
              >
                セッション一覧
              </Link>
            </nav>
          </div>
        </header>

        <main>
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default AppShell
