import { Injectable } from '@nestjs/common';

@Injectable()
export class StorageService {
  private storage: Map<string, any> = new Map();

  set(key: string, value: any): void {
    this.storage.set(key, value);
  }

  get(key: string): any {
    return this.storage.get(key);
  }

  delete(key: string): boolean {
    return this.storage.delete(key);
  }

  clear(): void {
    this.storage.clear();
  }

  getAll(): { [key: string]: any } {
    const obj: { [key: string]: any } = {};
    this.storage.forEach((value, key) => {
      obj[key] = value;
    });
    return obj;
  }
}
