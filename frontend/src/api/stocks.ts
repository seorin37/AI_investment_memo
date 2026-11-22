import type { MyStock, StockMaster, StockStatus } from '@/types/models';

type Query = Record<string, string | number | boolean | undefined | null>;

export interface StockHttpClient {
  get<T>(path: string, query?: Query): Promise<T>;
  post<T>(path: string, body?: unknown): Promise<T>;
  patch<T>(path: string, body?: unknown): Promise<T>;
  put<T>(path: string, body?: unknown): Promise<T>;
  del<T = void>(path: string): Promise<T>;
}

type StockMasterWire = StockMaster;
type MyStockWire = Omit<MyStock, 'tags' | 'unread_updates'> & {
  tags?: string[] | null;
  unread_updates?: number | null;
};

function master(payload: StockMasterWire): StockMaster {
  return { ...payload, code: payload.code.trim() };
}

function mine(payload: MyStockWire): MyStock {
  return {
    ...master(payload),
    status: payload.status,
    tags: payload.tags ?? [],
    unread_updates: payload.unread_updates ?? 0,
    added_at: payload.added_at,
  };
}

/** The six stock-master/user-stock endpoints implemented by FastAPI. */
export function createRealStockApi(http: StockHttpClient) {
  return {
    async listMyStocks(): Promise<MyStock[]> {
      return (await http.get<MyStockWire[]>('/stocks')).map(mine);
    },
    async searchStocks(q: string): Promise<StockMaster[]> {
      return (await http.get<StockMasterWire[]>('/stocks/search', { q })).map(master);
    },
    async getStock(code: string): Promise<StockMaster> {
      return master(await http.get<StockMasterWire>(`/stocks/${code}`));
    },
    async addStock(code: string, status: StockStatus): Promise<MyStock> {
      return mine(await http.post<MyStockWire>('/stocks', { code, status }));
    },
    async updateStock(
      code: string,
      patch: Partial<Pick<MyStock, 'status' | 'tags'>>,
    ): Promise<MyStock> {
      return mine(await http.patch<MyStockWire>(`/stocks/${code}`, patch));
    },
    removeStock(code: string): Promise<void> {
      return http.del(`/stocks/${code}`);
    },
    async reorderStocks(codes: string[]): Promise<MyStock[]> {
      return (await http.put<MyStockWire[]>('/stocks/order', { codes })).map(mine);
    },
  };
}
