import { ShellHeader } from "@/components/shell-header";
import { StatusBoard } from "@/components/status-board";
import webPackage from "../../package.json";

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <ShellHeader webVersion={webPackage.version} />
      <StatusBoard webVersion={webPackage.version} />
    </main>
  );
}
