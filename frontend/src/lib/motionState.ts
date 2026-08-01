export function newIds(previous: ReadonlySet<string>, current: readonly string[]) {
  return current.filter((id) => !previous.has(id));
}

export function didSemanticValueChange<T>(previous: T | undefined, current: T) {
  return previous !== undefined && previous !== current;
}
