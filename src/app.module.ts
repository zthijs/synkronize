import { Module } from '@nestjs/common';
import { APP_FILTER } from '@nestjs/core';
import { ProvidersModule } from './providers/providers.module';
import { ConsumersModule } from './consumers/consumers.module';
import { ConfigModule } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ScheduleModule } from '@nestjs/schedule';
import { Provider } from './providers/provider.entity';
import { Consumer } from './consumers/consumer.entity';
import { StorageModule } from './storage/storage.module';
import { SyncModule } from './sync/sync.module';
import { AllExceptionsFilter } from './common/filters/error.filter';

@Module({
  imports: [
    ConfigModule.forRoot(),
    TypeOrmModule.forRoot({
      type: 'sqlite',
      database: './data/data.db',
      entities: [Provider, Consumer],
      synchronize: process.env.NODE_ENV !== 'production',
    }),
    ScheduleModule.forRoot(),
    ProvidersModule,
    ConsumersModule,
    StorageModule,
    SyncModule,
  ],
  providers: [
    {
      provide: APP_FILTER,
      useClass: AllExceptionsFilter,
    },
  ],
})
export class AppModule {}
